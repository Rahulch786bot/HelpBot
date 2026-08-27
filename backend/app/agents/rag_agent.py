"""
RAG / Knowledge Agent.

Retrieves relevant context (vectorless -- see tools/retrieval.py),
answers with citations if confident, or signals low confidence and
hands back to the router so the query becomes a ticket instead of a
guess. This is a single LLM call that performs retrieval-selection,
confidence self-assessment, and answer drafting together, because for
a corpus this small a separate "retriever" pass buys nothing but an
extra round trip -- the model can just read everything and point at
what it used.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app import db
from app.config import RAG_CONFIDENCE_THRESHOLD, get_llm
from app.state import HelpBotState
from app.tools.retrieval import CORPUS_TEXT

RAG_SYSTEM_PROMPT = """You are the Knowledge Agent for HelpBot, Nimbus Corp's internal helpdesk \
assistant. You are given the FULL company knowledge base (policy/FAQ docs, split into numbered \
sections) plus a list of previously RESOLVED helpdesk tickets. Answer the employee's question \
using ONLY this material.

Rules:
- If the material answers the question, write a clear, concise answer (2-5 sentences) and list the \
sections you actually used as citations (by their [id], source file, and section heading).
- If two sources disagree, do not silently pick one. Say both figures/answers explicitly, note \
that they conflict, and tell the employee which one is more likely to apply to their specific \
situation if that's determinable (e.g. general policy vs. a specific onboarding exception) -- \
otherwise recommend they confirm with the relevant team.
- If the knowledge base does not contain enough to answer confidently, do NOT guess. Set \
confidence low and leave the answer generic.
- confidence is a number 0.0-1.0: how confident you are that your answer is complete and correct \
given ONLY the material provided. A partial/tangential match should score low, not medium.

Respond with ONLY a JSON object, no other text:
{
  "confidence": 0.0-1.0,
  "answer": "the answer to show the employee, or a short note that the info isn't available",
  "citations": [{"source": "filename.md", "section": "heading text"}]
}
"""


def _render_resolved_tickets() -> str:
    tickets = db.get_resolved_tickets()
    lines = []
    for t in tickets:
        lines.append(
            f"[ticket:{t['ticket_id']}] category={t['category']} | subject={t['subject']}\n"
            f"resolution: {t['resolution']}"
        )
    return "\n\n".join(lines)


def answer(state: HelpBotState) -> HelpBotState:
    llm = get_llm()
    context = (
        "=== POLICY / FAQ DOCUMENTS ===\n" + CORPUS_TEXT +
        "\n\n=== PREVIOUSLY RESOLVED TICKETS (second knowledge source) ===\n" +
        _render_resolved_tickets()
    )
    messages = [
        SystemMessage(content=RAG_SYSTEM_PROMPT),
        HumanMessage(content=f"KNOWLEDGE BASE:\n{context}\n\nEMPLOYEE QUESTION:\n{state['query']}"),
    ]
    raw = llm.invoke(messages).content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"confidence": 0.0, "answer": "", "citations": []}

    confidence = float(parsed.get("confidence", 0.0))
    state["rag_confidence"] = confidence
    state["rag_attempted"] = True

    trace = state.get("trace", [])

    if confidence >= RAG_CONFIDENCE_THRESHOLD and parsed.get("answer"):
        state["rag_answer"] = parsed["answer"]
        state["rag_citations"] = parsed.get("citations", [])
        state["final_answer"] = parsed["answer"]
        state["handled_by"] = "rag_agent"
        trace.append(f"RAG agent: answered directly (confidence={confidence:.2f})")
    else:
        state["rag_answer"] = None
        state["rag_citations"] = []
        trace.append(
            f"RAG agent: confidence too low ({confidence:.2f} < {RAG_CONFIDENCE_THRESHOLD}), "
            "handing back to router to raise a ticket"
        )
    state["trace"] = trace
    return state
