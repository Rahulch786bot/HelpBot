# HelpBot — Design Write-Up

## Key design decisions & tradeoffs

**Vectorless retrieval instead of a vector DB.** The knowledge base is small enough to fit
entirely in one prompt, and a reasoning pass over the whole corpus is better than top-k
similarity search at catching the deliberately planted cross-document inconsistency (the
expense-claim deadline conflict between `expense-policy.md` and `onboarding-guide.md`). The
tradeoff is that this doesn't scale — it works because the corpus is 4 short docs, and would
need to become a hybrid (cheap embedding pre-filter + this same reasoning pass over the
filtered candidates) if the knowledge base grew past what fits comfortably in a context window.

**One LLM call per agent hop, not agentic tool-loops everywhere.** The Router and RAG agent
each make a single structured-JSON call; the Ticket Agent makes at most one (field extraction)
plus a deterministic tool dispatch. This keeps latency and Groq free-tier rate-limit usage
predictable, and matches the brief's explicit instruction to keep the Ticket Agent "simple and
deterministic." The tradeoff is less flexibility — e.g. the Ticket Agent can't currently ask a
clarifying follow-up question mid-flow if field extraction is ambiguous; it does its best guess
from a single message.

**A confidence threshold, not a binary "found it / didn't."** The RAG agent self-reports a
0–1 confidence and only answers above a configurable threshold (default 0.55). This is a
judgment call baked into a prompt rather than a hard rule, which means it can occasionally be
mis-calibrated (see limitations below) — but it was preferred over a purely rules-based
check because "is this genuinely enough to answer confidently" is exactly the kind of judgment
that doesn't reduce well to keyword/overlap heuristics.

**SQLite over a managed/hosted DB.** Ticket actions needed to be real, persisted state changes,
but standing up Postgres (even free-tier RDS) adds infrastructure and cost risk for a 20-row
seed dataset. SQLite as a file next to the app gets the "real backend endpoint, real tool call"
requirement without any of that.

## What I'd improve with more time

- **Calibrate the RAG confidence threshold empirically.** Right now it's a single global
  number set by feel. With more time I'd build a small labeled eval set (in-scope vs.
  out-of-scope questions) and tune the threshold — and possibly separate "no relevant section
  found" from "found something but it's ambiguous/conflicting," which currently both collapse
  into "low confidence → ticket."
- **Multi-turn memory.** Each `/chat` call is currently stateless — if a user's first message is
  ambiguous (e.g. "check my ticket" with no ID), the agent asks for clarification but has no
  way to bind the next message back to that in-flight request. I'd add a lightweight
  session/thread id so a clarifying answer resumes the same graph run instead of starting over.
- **Duplicate/similar-ticket surfacing.** Explicitly out of scope for this assignment, but a
  natural next step: before creating a ticket, show the user the most similar *resolved*
  ticket (which the RAG agent already has access to) so they can self-serve instead.
- **Structured tool-calling instead of hand-parsed JSON.** The Router/RAG/field-extraction
  calls currently ask the LLM to emit raw JSON in a system prompt and parse it defensively.
  Groq's OpenAI-compatible function-calling / structured-output mode would make this more
  robust against formatting drift, at the cost of slightly more provider-specific code.

## Known limitations & failure cases

- **Confidence self-assessment can be wrong in either direction.** An LLM confidently
  misjudging its own certainty is a known failure mode; a wrong "high confidence" answer would
  surface a stale/incorrect answer instead of raising a ticket, and a wrong "low confidence"
  would create an unnecessary ticket for something actually answerable. The prompt is written
  to be conservative (partial/tangential matches should score low), but this isn't a guarantee.
- **Router misclassification, especially the sensitive-escalation category.** The guardrail is
  only as good as the router's classification of a message as HR-grievance-related. It's
  instructed to be the tie-breaker "when in doubt," but a sufficiently indirectly-phrased
  grievance could still be misrouted to the RAG or Ticket agent instead of the guardrail.
- **No de-duplication of tickets.** As specified, the same underlying issue reported twice
  creates two separate tickets — by design for this assignment, but a real deployment would
  want to catch this.
- **Single free-tier LLM provider, no fallback.** If Groq's free tier is rate-limited or down,
  the whole system fails open into "I couldn't process that" rather than falling back to a
  second provider. `LLM_PROVIDER` in `config.py` is structured to make adding a fallback
  straightforward, but it isn't implemented.
- **No authentication.** Anyone who can reach the deployed URL can create/escalate/cancel
  tickets. Fine for a take-home demo; not fine for a real internal tool, which would need to
  tie ticket actions to an authenticated employee identity.
