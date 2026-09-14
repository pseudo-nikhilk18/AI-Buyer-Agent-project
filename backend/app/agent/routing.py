from app.agent.state import PurchasingState
from app.config import get_settings
from app.domain.schemas import AuthorizationResult, EvidenceAssessment


MAX_INVESTIGATION_ATTEMPTS = 2


def route_after_evidence(state: PurchasingState) -> str:
    assessment = EvidenceAssessment.model_validate(state["evidence_assessment"])
    if assessment.complete:
        return "calculate"
    if (
        assessment.missing_tools
        and state.get("investigation_attempts", 0) < MAX_INVESTIGATION_ATTEMPTS
    ):
        return "replan"
    return "propose"


def route_after_authorization(state: PurchasingState) -> str:
    authorization = AuthorizationResult.model_validate(state["authorization"])
    if authorization.status in {"auto_authorized", "human_approved"}:
        return "execute"
    return "finalize"


def route_after_execution(state: PurchasingState) -> str:
    if state["action"]["status"] != "replan_required":
        return "validate_outcome"
    if state["replan_count"] <= get_settings().max_replans:
        return "gather_evidence"
    return "finalize"
