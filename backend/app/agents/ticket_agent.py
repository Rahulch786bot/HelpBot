"""
Ticket Agent.

Handles everything ticket-related via real tool calls against the
SQLite-backed ticket store (app/tools/ticket_tools.py):
  - creates a new ticket, either because the router sent a fresh
    issue/request, or because the RAG agent handed back a
    low-confidence self-serve question.
  - for an existing ticket, checks status / escalates / cancels.

Field extraction (category/subject/description) uses one LLM call.
Everything after that -- which tool to call, how to interpret the
result -- is plain deterministic Python, per the assignment's
instruction to keep this agent simple and deterministic.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_llm
from app.state import HelpBotState
from app.tools.ticket_tools import (
    cancel_ticket_tool,
    create_ticket_tool,
    escalate_ticket_tool,
    get_ticket_status_tool,
)

EXTRACT_SYSTEM_PROMPT = """You are extracting structured fields from an employee's helpdesk \
message so a ticket can be created. Respond with ONLY a JSON object, no other text:
{
  "category": one of ["IT - Access", "IT - Hardware", "IT - Software", "IT - Onboarding",
                       "HR - Leave", "HR - Access", "Finance - Reimbursement",
                       "Finance - Reimbursement Delay", "General"],
  "subject": "short one-line summary, under 12 words",
  "description": "1-2 sentence restatement of the issue/request in clear terms",
  "priority": "Low" | "Medium" | "High" | "Critical"
}
Use "Critical" only for something described as a full outage / total inability to work. \
Otherwise default to "Medium".
"""


def _extract_ticket_fields(query: str) -> dict:
    llm = get_llm()
    raw = llm.invoke([
        SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]).content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "category": "General",
            "subject": query[:60],
            "description": query,
            "priority": "Medium",
        }


def handle(state: HelpBotState) -> HelpBotState:
    trace = state.get("trace", [])
    intent = state["intent"]

    # --- Case 1: existing-ticket action (status / escalate / cancel) -----
    if intent == "ticket_status_check":
        ticket_id = state.get("ticket_id")
        action = state.get("ticket_action") or "status"

        if not ticket_id:
            state["final_answer"] = (
                "I couldn't find a ticket number in your message. Could you share the "
                "ticket ID (e.g. TCK-1015) you'd like me to look up?"
            )
            state["handled_by"] = "ticket_agent"
            trace.append("Ticket agent: no ticket_id extracted, asked user to clarify")
            state["trace"] = trace
            return state

        tool_map = {
            "status": get_ticket_status_tool,
            "escalate": escalate_ticket_tool,
            "cancel": cancel_ticket_tool,
        }
        result = tool_map[action].invoke({"ticket_id": ticket_id})
        state["ticket_result"] = result
        state["ticket_action"] = action

        if not result.get("found"):
            state["final_answer"] = (
                f"I couldn't find a ticket with ID {ticket_id.upper()}. Please double-check "
                "the ticket number -- if you don't have one, I can raise a new ticket instead."
            )
        elif action == "status":
            state["final_answer"] = (
                f"Ticket {result['ticket_id']} ({result['subject']}) is currently "
                f"**{result['status']}**." +
                (f" Resolution: {result['resolution']}" if result.get("resolution") else "")
            )
        elif not result.get("allowed", True):
            state["final_answer"] = (
                f"Ticket {result['ticket_id']} is already **{result['status']}**, so it can't "
                f"be {'escalated' if action == 'escalate' else 'cancelled'}."
            )
        elif action == "escalate":
            state["final_answer"] = (
                f"Ticket {result['ticket_id']} has been escalated and is now marked "
                f"**{result['status']}** with priority {result['priority']}. The team will "
                "prioritize it accordingly."
            )
        else:  # cancel
            state["final_answer"] = f"Ticket {result['ticket_id']} has been **cancelled** as requested."

        state["handled_by"] = "ticket_agent"
        trace.append(f"Ticket agent: action={action} ticket_id={ticket_id} -> {result.get('found')}")
        state["trace"] = trace
        return state

    # --- Case 2: new ticket (either a genuine new issue, or a RAG fallback)
    fields = _extract_ticket_fields(state["query"])
    created = create_ticket_tool.invoke({
        "category": fields.get("category", "General"),
        "subject": fields.get("subject", state["query"][:60]),
        "description": fields.get("description", state["query"]),
        "priority": fields.get("priority", "Medium"),
    })
    state["ticket_result"] = created
    state["ticket_id"] = created["ticket_id"]
    state["ticket_action"] = "create"

    if state.get("rag_attempted"):
        prefix = (
            "I wasn't able to find a confident answer to that in our policy docs, so "
            "I've raised a ticket for the team to help directly. "
        )
    else:
        prefix = "I've raised a ticket for this. "

    state["final_answer"] = (
        f"{prefix}Ticket **{created['ticket_id']}** ({created['category']}, "
        f"priority {created['priority']}) has been created and is now **{created['status']}**."
    )
    state["handled_by"] = "ticket_agent"
    trace.append(f"Ticket agent: created {created['ticket_id']} (rag_fallback={state.get('rag_attempted', False)})")
    state["trace"] = trace
    return state
