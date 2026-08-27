"""
Router / Intent Detection Agent.

Entry point for every query (and also the re-entry point when the RAG
agent hands a low-confidence query back). Classifies into one of four
intents and, for ticket-status queries, extracts the ticket ID and the
requested action up front so the Ticket Agent doesn't have to re-parse
the raw user text.

The fourth intent, "sensitive_escalation", exists because of an explicit
requirement in hr-faq.md: grievance / harassment / misconduct queries
must never be answered, mediated, or documented by an automated system
-- they must go straight to a human. This is treated as a hard routing
rule, not something the RAG or Ticket agent could quietly override.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_llm
from app.state import HelpBotState

ROUTER_SYSTEM_PROMPT = """You are the intent router for HelpBot, an internal helpdesk assistant \
for a company called Nimbus Corp. Classify the employee's query into exactly one of:

- "sensitive_escalation": the query describes or asks about harassment, discrimination, \
retaliation, or other workplace misconduct/grievance matters -- of ANY kind, however mild it \
sounds. Nimbus Corp policy is that these must NEVER be answered or handled by an automated \
system, only by a human HR rep or the Ethics Hotline. When in doubt between this and another \
category, choose this one.
- "ticket_status_check": the employee is asking about an EXISTING ticket -- checking its status, \
asking to escalate it, or asking to cancel it. Extract the ticket_id (format TCK-####) if present, \
and the action: "status", "escalate", or "cancel".
- "new_ticket": the employee is reporting a new issue or making a new request that isn't a question \
answerable from policy docs (e.g. something broken, a request for something to be done for them).
- "self_serve_question": the employee is asking a factual/policy question that could plausibly be \
answered from Nimbus Corp's IT/HR/Expense/Onboarding documentation or past resolved tickets.

Respond with ONLY a JSON object, no other text:
{
  "intent": "sensitive_escalation" | "ticket_status_check" | "new_ticket" | "self_serve_question",
  "ticket_id": "TCK-####" or null,
  "ticket_action": "status" | "escalate" | "cancel" or null,
  "reasoning": "one short sentence"
}
"""


def route(state: HelpBotState) -> HelpBotState:
    llm = get_llm()
    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=state["query"]),
    ]
    raw = llm.invoke(messages).content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Fail safe: if the router itself can't produce valid JSON, don't
        # silently guess -- fall back to routing as a new ticket so a
        # human ends up looking at it instead of the system hallucinating.
        parsed = {
            "intent": "new_ticket",
            "ticket_id": None,
            "ticket_action": None,
            "reasoning": "Router output could not be parsed; failing safe to ticket creation.",
        }

    state["intent"] = parsed.get("intent", "new_ticket")
    state["router_reasoning"] = parsed.get("reasoning", "")
    state["ticket_id"] = parsed.get("ticket_id")
    state["ticket_action"] = parsed.get("ticket_action")

    trace = state.get("trace", [])
    trace.append(f"Router: intent={state['intent']} ({state['router_reasoning']})")
    state["trace"] = trace
    return state


def route_decision(state: HelpBotState) -> str:
    """Conditional-edge function: where does the graph go after routing?"""
    if state.get("rag_attempted") and state["intent"] == "self_serve_question":
        # RAG already tried once and handed back -- don't loop, go straight
        # to the Ticket agent to raise a ticket instead.
        return "ticket_agent"
    return {
        "self_serve_question": "rag_agent",
        "new_ticket": "ticket_agent",
        "ticket_status_check": "ticket_agent",
        "sensitive_escalation": "sensitive_handler",
    }[state["intent"]]
