"""
Real backend actions available to the Ticket Agent. These are plain
Python functions (exposed to the LLM as LangChain @tool-decorated
functions) that hit the SQLite ticket store -- not text the LLM
generates and pretends is a ticket action.
"""
from langchain_core.tools import tool

from app import db

VALID_CATEGORIES = [
    "IT - Access", "IT - Hardware", "IT - Software", "IT - Onboarding",
    "HR - Leave", "HR - Access", "Finance - Reimbursement", "Finance - Reimbursement Delay",
    "General",
]


@tool
def create_ticket_tool(category: str, subject: str, description: str, priority: str = "Medium") -> dict:
    """Create a new helpdesk ticket. category should be one of the standard
    Nimbus Corp categories (IT - Access, IT - Hardware, IT - Software,
    IT - Onboarding, HR - Leave, HR - Access, Finance - Reimbursement,
    Finance - Reimbursement Delay, General). priority is Low/Medium/High/Critical."""
    if category not in VALID_CATEGORIES:
        category = "General"
    return db.create_ticket(category, subject, description, priority)


@tool
def get_ticket_status_tool(ticket_id: str) -> dict:
    """Look up a ticket by its ID (e.g. TCK-1015) and return its current
    status. Returns {"found": False} if no such ticket exists -- never
    invent a status for a ticket that isn't in the store."""
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        return {"found": False, "ticket_id": ticket_id}
    return {"found": True, **ticket}


@tool
def escalate_ticket_tool(ticket_id: str) -> dict:
    """Escalate an existing, non-closed ticket (sets status to Escalated
    and bumps priority). Returns {"found": False} if the ticket doesn't
    exist, or {"found": True, "allowed": False, ...} if it's already
    Resolved/Cancelled and can't be escalated."""
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        return {"found": False, "ticket_id": ticket_id}
    if ticket["status"] in ("Resolved", "Cancelled"):
        return {"found": True, "allowed": False, **ticket}
    updated = db.update_ticket_status(ticket_id, "Escalated")
    return {"found": True, "allowed": True, **updated}


@tool
def cancel_ticket_tool(ticket_id: str) -> dict:
    """Cancel an existing, non-closed ticket. Returns {"found": False} if
    the ticket doesn't exist, or {"found": True, "allowed": False, ...}
    if it's already Resolved/Cancelled."""
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        return {"found": False, "ticket_id": ticket_id}
    if ticket["status"] in ("Resolved", "Cancelled"):
        return {"found": True, "allowed": False, **ticket}
    updated = db.update_ticket_status(ticket_id, "Cancelled")
    return {"found": True, "allowed": True, **updated}


TICKET_TOOLS = [create_ticket_tool, get_ticket_status_tool, escalate_ticket_tool, cancel_ticket_tool]
