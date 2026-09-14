from uuid import UUID

from app.database import session_scope
from app.domain.schemas import ActionResult, OutcomeValidation
from app.models import PurchaseOrder


def validate_purchase_outcome(action: ActionResult) -> OutcomeValidation:
    if action.action_type == "none" or action.purchase_order_id is None:
        return OutcomeValidation(
            status="not_required",
            expected_quantity=None,
            actual_quantity=None,
            detail="No purchasing mutation required validation.",
        )

    with session_scope() as session:
        order = session.get(PurchaseOrder, UUID(action.purchase_order_id))
        if order is None:
            return OutcomeValidation(
                status="failed",
                expected_quantity=action.requested_quantity,
                actual_quantity=None,
                detail="The acknowledged purchase order could not be read back.",
            )
        if order.quantity != action.requested_quantity or order.status != "confirmed":
            return OutcomeValidation(
                status="failed",
                expected_quantity=action.requested_quantity,
                actual_quantity=order.quantity,
                detail="The persisted purchase order differs from the authorized action.",
            )
        return OutcomeValidation(
            status="validated",
            expected_quantity=action.requested_quantity,
            actual_quantity=order.quantity,
            detail="The persisted purchase order matches the authorized action.",
        )
