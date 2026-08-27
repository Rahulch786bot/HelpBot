"""
Shared state that flows through the LangGraph graph. Every agent node
reads from and writes to this single TypedDict -- this is the "clear
state passed between agents" the assignment asks for, and it's also
what gets logged/returned to the frontend so the routing decision is
visible, not hidden inside a black box.
"""
from typing import Literal, Optional, TypedDict


Intent = Literal["self_serve_question", "new_ticket", "ticket_status_check", "sensitive_escalation"]
TicketAction = Literal["status", "escalate", "cancel", "create"]


class Citation(TypedDict):
    source: str
    section: str


class HelpBotState(TypedDict, total=False):
    # ---- input ----
    query: str

    # ---- router output ----
    intent: Intent
    router_reasoning: str

    # ---- RAG agent ----
    rag_answer: Optional[str]
    rag_citations: list[Citation]
    rag_confidence: float
    rag_attempted: bool  # so the router doesn't loop forever on a RAG fallback

    # ---- ticket agent ----
    ticket_action: Optional[TicketAction]
    ticket_id: Optional[str]      # referenced ticket, if any (status/escalate/cancel)
    ticket_category: Optional[str]
    ticket_subject: Optional[str]
    ticket_result: Optional[dict]  # raw result from the ticket tool call

    # ---- final response shown to the user ----
    final_answer: str
    handled_by: str  # which agent produced the final answer, for the UI/trace
    trace: list[str]  # human-readable log of the routing/handoff path
