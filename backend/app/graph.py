"""
The HelpBot LangGraph graph.

Nodes:
  router_agent  -> classifies intent, extracts ticket refs
  rag_agent     -> answers self-serve questions, or hands back to router
  ticket_agent  -> creates/looks up/escalates/cancels tickets
  sensitive_guardrail -> fixed, policy-compliant response for
                          harassment/grievance queries (per hr-faq.md,
                          §4: these must NEVER be handled by an
                          automated system). This is a deterministic
                          safety short-circuit, not a fourth "agent" in
                          the assignment's sense -- it makes no LLM call
                          and does no reasoning about the query content.

Edges:
  START -> router_agent
  router_agent -> (conditional) rag_agent | ticket_agent | sensitive_guardrail
  rag_agent -> (conditional) END (answered) | router_agent (low confidence, re-route)
  ticket_agent -> END
  sensitive_guardrail -> END

The router -> rag_agent -> router -> ticket_agent loop is the explicit
"RAG agent ... signals low confidence and hands back to the router so
the query becomes a ticket instead" handoff required by the brief. The
`rag_attempted` flag on state prevents it from looping more than once.
"""
from langgraph.graph import END, StateGraph

from app.agents import rag_agent, router_agent, ticket_agent
from app.state import HelpBotState

ETHICS_HOTLINE_MESSAGE = (
    "I'm not able to help with this directly. Nimbus Corp policy requires that reports of "
    "harassment, discrimination, or workplace misconduct be handled by a human, not an "
    "automated system.\n\n"
    "Please contact a human HR representative or use the confidential Ethics Hotline "
    "(available 24/7 via the HR portal's \"Report a Concern\" section) so this can be looked "
    "into properly."
)


def sensitive_guardrail(state: HelpBotState) -> HelpBotState:
    trace = state.get("trace", [])
    trace.append("Guardrail: sensitive HR matter detected, routed to human channel (no auto-handling)")
    state["trace"] = trace
    state["final_answer"] = ETHICS_HOTLINE_MESSAGE
    state["handled_by"] = "sensitive_guardrail"
    return state


def rag_decision(state: HelpBotState) -> str:
    """After the RAG agent runs: did it answer, or does it need to hand back?"""
    if state.get("rag_answer"):
        return "end"
    return "router_agent"


def build_graph():
    graph = StateGraph(HelpBotState)

    graph.add_node("router_agent", router_agent.route)
    graph.add_node("rag_agent", rag_agent.answer)
    graph.add_node("ticket_agent", ticket_agent.handle)
    graph.add_node("sensitive_guardrail", sensitive_guardrail)

    graph.set_entry_point("router_agent")

    graph.add_conditional_edges(
        "router_agent",
        router_agent.route_decision,
        {
            "rag_agent": "rag_agent",
            "ticket_agent": "ticket_agent",
            "sensitive_handler": "sensitive_guardrail",
        },
    )
    graph.add_conditional_edges(
        "rag_agent",
        rag_decision,
        {"end": END, "router_agent": "router_agent"},
    )
    graph.add_edge("ticket_agent", END)
    graph.add_edge("sensitive_guardrail", END)

    return graph.compile()


helpbot_graph = build_graph()


def run_query(query: str) -> HelpBotState:
    initial_state: HelpBotState = {"query": query, "trace": []}
    result = helpbot_graph.invoke(initial_state)
    return result
