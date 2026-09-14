from functools import partial

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.authorization import authorize_action
from app.agent.nodes.decision import (
    calculate_requirement,
    propose_decision,
    validate_plan,
)
from app.agent.nodes.evidence import assess_collected_evidence, gather_evidence
from app.agent.nodes.execution import execute_action, finalize_run, validate_outcome
from app.agent.nodes.planning import plan_investigation
from app.agent.provider import ResolvedProvider
from app.agent.routing import (
    route_after_authorization,
    route_after_evidence,
    route_after_execution,
)
from app.agent.state import PurchasingState


def build_purchasing_graph(checkpointer, provider: ResolvedProvider | None):
    graph = StateGraph(PurchasingState)
    graph.add_node(
        "plan_investigation",
        partial(plan_investigation, provider=provider),
    )
    graph.add_node("gather_evidence", gather_evidence)
    graph.add_node("assess_evidence", assess_collected_evidence)
    graph.add_node("calculate_requirement", calculate_requirement)
    graph.add_node(
        "propose_decision",
        partial(propose_decision, provider=provider),
    )
    graph.add_node("validate_plan", validate_plan)
    graph.add_node("authorize_action", authorize_action)
    graph.add_node("execute_action", execute_action)
    graph.add_node("validate_outcome", validate_outcome)
    graph.add_node("finalize", finalize_run)

    graph.add_edge(START, "plan_investigation")
    graph.add_edge("plan_investigation", "gather_evidence")
    graph.add_edge("gather_evidence", "assess_evidence")
    graph.add_conditional_edges(
        "assess_evidence",
        route_after_evidence,
        {"calculate": "calculate_requirement", "propose": "propose_decision"},
    )
    graph.add_edge("calculate_requirement", "propose_decision")
    graph.add_edge("propose_decision", "validate_plan")
    graph.add_edge("validate_plan", "authorize_action")
    graph.add_conditional_edges(
        "authorize_action",
        route_after_authorization,
        {"execute": "execute_action", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "execute_action",
        route_after_execution,
        {
            "gather_evidence": "gather_evidence",
            "validate_outcome": "validate_outcome",
            "finalize": "finalize",
        },
    )
    graph.add_edge("validate_outcome", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
