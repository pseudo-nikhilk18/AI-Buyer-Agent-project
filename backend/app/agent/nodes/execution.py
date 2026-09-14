from uuid import UUID

from app.agent.state import PurchasingState, append_step
from app.domain.schemas import (
    ActionResult,
    AuthorizationResult,
    OutcomeValidation,
    PurchaseCandidate,
)
from app.services.action import (
    execute_purchase,
    make_idempotency_key,
)
from app.services.validation import validate_purchase_outcome


def execute_action(state: PurchasingState) -> PurchasingState:
    selected = PurchaseCandidate.model_validate(state["selected_candidate"])
    idempotency_key = make_idempotency_key(
        UUID(state["case_id"]),
        selected.quantity,
        state["evidence"],
    )
    action = execute_purchase(
        UUID(state["run_id"]),
        UUID(state["case_id"]),
        selected.quantity,
        idempotency_key,
    )
    replan_count = state.get("replan_count", 0)
    if action.status == "replan_required":
        replan_count += 1
    return {
        "action": action.model_dump(mode="json"),
        "replan_count": replan_count,
        "steps": append_step(state, "execute_action"),
    }


def validate_outcome(state: PurchasingState) -> PurchasingState:
    validation = validate_purchase_outcome(ActionResult.model_validate(state["action"]))
    return {
        "validation": validation.model_dump(mode="json"),
        "steps": append_step(state, "validate_outcome"),
    }


def finalize_run(state: PurchasingState) -> PurchasingState:
    authorization = AuthorizationResult.model_validate(state["authorization"])
    validation = state.get("validation")
    if validation and validation["status"] == "validated":
        status = "completed"
    elif validation and validation["status"] == "failed":
        status = "escalated"
    elif authorization.status == "not_required":
        status = "completed"
    elif authorization.status == "rejected":
        status = "rejected"
    elif state.get("action", {}).get("status") == "replan_required":
        status = "escalated"
    else:
        status = "blocked"

    result: PurchasingState = {
        "status": status,
        "steps": append_step(state, "finalize"),
    }
    if validation is None and authorization.status in {
        "not_required",
        "rejected",
        "blocked",
    }:
        result["validation"] = OutcomeValidation(
            status="not_required",
            expected_quantity=None,
            actual_quantity=None,
            detail="No purchasing mutation occurred, so read-back validation was not required.",
        ).model_dump(mode="json")
    elif validation is None and state.get("action", {}).get("status") == "replan_required":
        result["validation"] = OutcomeValidation(
            status="not_required",
            expected_quantity=state["action"].get("requested_quantity"),
            actual_quantity=None,
            detail="No mutation occurred because current evidence invalidated the action.",
        ).model_dump(mode="json")
    return result
