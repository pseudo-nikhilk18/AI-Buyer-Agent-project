from uuid import UUID

from app.agent.state import PurchasingState, append_step
from app.database import session_scope
from app.domain.evidence import assess_evidence
from app.domain.schemas import CaseContext, InvestigationPlan
from app.purchasing_tools import EvidenceNotFoundError, REQUIRED_TOOL_NAMES, TOOL_REGISTRY


def gather_evidence(state: PurchasingState) -> PurchasingState:
    evidence: dict[str, dict] = dict(state.get("evidence", {}))
    plan = InvestigationPlan.model_validate(state["investigation_plan"])
    tool_names = plan.tool_names
    if state.get("action", {}).get("status") == "replan_required":
        tool_names = REQUIRED_TOOL_NAMES
    with session_scope() as session:
        for tool_name in tool_names:
            tool = TOOL_REGISTRY[tool_name]
            try:
                result = tool(session, UUID(state["case_id"]))
                evidence[tool_name] = result.model_dump(mode="json")
            except EvidenceNotFoundError as error:
                evidence[tool_name] = {"error": str(error)}

    return {
        "evidence": evidence,
        "steps": append_step(state, "gather_evidence"),
    }


def assess_collected_evidence(state: PurchasingState) -> PurchasingState:
    assessment = assess_evidence(
        context=CaseContext.model_validate(state["context"]),
        evidence=state["evidence"],
    )
    return {
        "evidence_assessment": assessment.model_dump(mode="json"),
        "steps": append_step(state, "assess_evidence"),
    }
