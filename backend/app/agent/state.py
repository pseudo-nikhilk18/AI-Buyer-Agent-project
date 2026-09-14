from typing import TypedDict


class PurchasingState(TypedDict, total=False):
    run_id: str
    case_id: str
    mode: str
    provider: str | None
    model: str | None
    context: dict
    investigation_plan: dict
    evidence: dict[str, dict]
    evidence_assessment: dict
    analysis: dict
    decision: dict
    selected_candidate: dict | None
    preliminary_authorization: dict
    authorization: dict
    human_review: dict
    action: dict
    validation: dict
    status: str
    error_code: str | None
    replan_count: int
    steps: list[str]


def append_step(state: PurchasingState, step: str) -> list[str]:
    return [*state.get("steps", []), step]
