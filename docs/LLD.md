# HelpBot — Low-Level Design

## 1. Agent State Schema

Defined in `backend/app/state.py` as a `TypedDict` (`total=False`, so nodes only need to set
the fields relevant to what they did):

```python
class HelpBotState(TypedDict, total=False):
    # input
    query: str

    # router output
    intent: Literal["self_serve_question", "new_ticket", "ticket_status_check", "sensitive_escalation"]
    router_reasoning: str

    # RAG agent
    rag_answer: Optional[str]
    rag_citations: list[Citation]        # [{"source": "hr-faq.md", "section": "1. Leave Policy"}]
    rag_confidence: float                # 0.0-1.0
    rag_attempted: bool                  # guards the router<->RAG loop to one pass

    # ticket agent
    ticket_action: Optional[Literal["status", "escalate", "cancel", "create"]]
    ticket_id: Optional[str]
    ticket_category: Optional[str]
    ticket_subject: Optional[str]
    ticket_result: Optional[dict]        # raw tool result

    # output
    final_answer: str
    handled_by: str                      # "rag_agent" | "ticket_agent" | "sensitive_guardrail"
    trace: list[str]                     # human-readable log of every node's decision
```

This entire object is what `run_query()` returns; the API layer picks the fields it needs for
the response contract (§4) but the full `trace` and `rag_citations` are surfaced to the
frontend for transparency.

## 2. Graph Definition (`backend/app/graph.py`)

Nodes: `router_agent`, `rag_agent`, `ticket_agent`, `sensitive_guardrail`.

Edges:
- `START → router_agent`
- `router_agent →` (conditional, `route_decision`) `→ rag_agent | ticket_agent | sensitive_guardrail`
  - if `rag_attempted` is already `True` and intent is `self_serve_question`, forces `ticket_agent`
    (prevents infinite RAG↔router looping)
- `rag_agent →` (conditional, `rag_decision`) `→ END` (if `rag_answer` set) `| router_agent` (hand-back)
- `ticket_agent → END`
- `sensitive_guardrail → END`

## 3. Agent Logic & Prompts

### 3.1 Router Agent (`agents/router_agent.py`)

One LLM call, temperature 0.1, strict-JSON system prompt (full text in source). Classifies into
4 intents; for `ticket_status_check` also extracts `ticket_id` (regex-shaped `TCK-####`) and
`ticket_action` (`status`/`escalate`/`cancel`). `sensitive_escalation` is explicitly instructed
to be the tie-breaker "when in doubt" against the other categories, since the cost of a false
negative here (an automated system responding to a harassment report) is much higher than a
false positive (an ordinary IT question routed to a human unnecessarily).

**Failure mode handling:** if the LLM's output isn't valid JSON, the router does *not* retry or
guess — it fails safe by classifying as `new_ticket`, so a human ends up looking at the query
instead of the system silently doing nothing or hallucinating an answer.

### 3.2 RAG / Knowledge Agent (`agents/rag_agent.py`)

One LLM call per attempt. Context = every doc section (from `tools/retrieval.py`, `##`-split,
each tagged `[id] source=... | section=...`) + every `Resolved` ticket's subject/resolution
(`db.get_resolved_tickets()`). System prompt instructs the model to:
- answer only from the given material,
- explicitly surface disagreements between sources rather than silently picking one (this is
  what makes the deliberate expense-deadline inconsistency in the content pack visible to the
  user instead of masked),
- return `{"confidence": float, "answer": str, "citations": [{"source", "section"}]}`.

`rag_confidence >= RAG_CONFIDENCE_THRESHOLD` (default `0.55`, env-configurable) → answer is
final. Otherwise `rag_answer = None`, `rag_attempted = True`, and the graph routes back to the
router, which (guarded by `rag_attempted`) sends the query to the Ticket agent.

### 3.3 Ticket Agent (`agents/ticket_agent.py`)

Two paths:

- **`ticket_status_check`**: `ticket_id`/`ticket_action` already come from the router. No LLM
  call at all — pure deterministic dispatch to one of `get_ticket_status_tool` /
  `escalate_ticket_tool` / `cancel_ticket_tool`. If `ticket_id` is missing (router couldn't
  extract one), the agent asks the user to clarify rather than guessing a ticket. If the tool
  reports `found: False`, the agent tells the user plainly rather than fabricating a status —
  this is the required handling for `TCK-9999`-style queries.
- **`new_ticket` / RAG fallback**: one LLM call (`_extract_ticket_fields`) turns the raw query
  into `{category, subject, description, priority}` (category constrained to the fixed Nimbus
  Corp category list from `it-policy.md`/`hr-faq.md`/`expense-policy.md`), then
  `create_ticket_tool` is called. The response message differs slightly depending on whether
  this was a genuine new issue or a RAG low-confidence hand-back, so the user understands why a
  ticket was raised instead of an answer.

## 4. Tools (`backend/app/tools/`)

`ticket_tools.py` — LangChain `@tool`-decorated functions backing the Ticket Agent, each a thin
wrapper over `db.py`:

| Tool | Purpose |
|---|---|
| `create_ticket_tool(category, subject, description, priority)` | Inserts a new row, `status="Open"`, auto-incremented `TCK-####` id. |
| `get_ticket_status_tool(ticket_id)` | Returns `{"found": False}` or the full ticket row. |
| `escalate_ticket_tool(ticket_id)` | No-ops with `allowed: False` if already `Resolved`/`Cancelled`; else sets `status="Escalated"`. |
| `cancel_ticket_tool(ticket_id)` | Same guard; sets `status="Cancelled"`. |

`retrieval.py` — loads and section-splits the 4 markdown docs at import time into a module-level
`CORPUS` / `CORPUS_TEXT` (see HLD §4 for the retrieval-strategy rationale).

## 5. Data / Storage

**Ticket store** — SQLite (`app/data/tickets.db`), single table:

```sql
CREATE TABLE tickets (
    ticket_id     TEXT PRIMARY KEY,   -- e.g. "TCK-1015"
    category      TEXT,
    subject       TEXT,
    description   TEXT,
    status        TEXT,               -- Open | In Progress | Escalated | Resolved | Cancelled
    priority      TEXT,               -- Low | Medium | High | Critical
    created_date  TEXT,               -- YYYY-MM-DD
    resolution    TEXT                -- NULL until Resolved
);
```

Seeded once from `tickets.json` on first startup (`db.init_db()`, called from the FastAPI
`lifespan` hook); idempotent — re-running with an existing populated DB is a no-op.

**Knowledge base** — flat files (`app/data/docs/*.md`), no database; loaded into memory at
process start (see §4).

## 6. API Contracts (FastAPI, `backend/app/main.py`)

### `POST /chat`

Request:
```json
{ "query": "What's the status of ticket TCK-1015?" }
```

Response (`200`):
```json
{
  "final_answer": "Ticket TCK-1015 (Zoom outage during scheduled meeting) is currently **Open**.",
  "intent": "ticket_status_check",
  "handled_by": "ticket_agent",
  "trace": [
    "Router: intent=ticket_status_check (status check)",
    "Ticket agent: action=status ticket_id=TCK-1015 -> True"
  ],
  "rag_citations": [],
  "rag_confidence": null,
  "ticket_result": { "ticket_id": "TCK-1015", "status": "Open", "...": "..." }
}
```
`400` if `query` is empty/whitespace-only.

### `GET /tickets/{ticket_id}`

Direct read of a single ticket (used for debugging/inspection, not by the chat flow itself,
which goes through the graph). `404` if not found.

### `GET /health`

Liveness check for the deployment (`{"status": "ok"}`).

## 7. Frontend Contract

The React app (`frontend/src/App.jsx`) is a single chat view. Each bot message renders an
expandable "routing trace" pulled straight from `trace` + `rag_citations` in the `/chat`
response, so which agent handled the query — and, for RAG answers, exactly which document
sections were cited — is visible inline, not hidden. `VITE_API_URL` (build-time env var) points
it at the backend; defaults to `http://localhost:8000` for local dev.
