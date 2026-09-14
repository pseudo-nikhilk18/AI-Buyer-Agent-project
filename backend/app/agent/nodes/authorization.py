from langgraph.types import interrupt

from app.agent.state import PurchasingState, append_step
from app.domain.schemas import AuthorizationResult, PurchaseCandidate, ReviewDecision


def authorize_action(state: PurchasingState) -> PurchasingState:
    authorization = AuthorizationResult.model_validate(state["preliminary_authorization"])
    if authorization.status != "human_review":
        return {
            "authorization": authorization.model_dump(mode="json"),
            "steps": append_step(state, "authorize_action"),
        }

    selected = PurchaseCandidate.model_validate(state["selected_candidate"])
    review_payload = {
        "case_id": state["case_id"],
        "decision": state["decision"],
        "proposed_quantity": selected.quantity,
        "proposed_spend_minor": selected.spend_minor,
        "currency": selected.currency,
        "reason_codes": authorization.reason_codes,
    }
    review = ReviewDecision.model_validate(interrupt(review_payload))
    if review.decision == "approve":
        final_authorization = AuthorizationResult(
            status="human_approved",
            reason_codes=["buyer_approved", *authorization.reason_codes],
            detail="The buyer approved the exact proposed action.",
        )
    else:
        final_authorization = AuthorizationResult(
            status="rejected",
            reason_codes=["buyer_rejected"],
            detail="The buyer rejected the proposed action.",
        )
    return {
        "authorization": final_authorization.model_dump(mode="json"),
        "human_review": review.model_dump(mode="json"),
        "steps": append_step(state, "authorize_action"),
    }
