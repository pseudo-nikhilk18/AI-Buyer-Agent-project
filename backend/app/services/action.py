import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from app.database import session_scope
from app.domain.evidence import assess_evidence
from app.domain.policy import analyze_purchase
from app.domain.schemas import (
    ActionResult,
    BudgetEvidence,
    CapacityEvidence,
    CaseContext,
    ForecastEvidence,
    InventoryEvidence,
    OpenOrdersEvidence,
    SupplierEvidence,
)
from app.models import (
    ActionAttempt,
    BudgetSnapshot,
    CapacitySnapshot,
    PurchaseOrder,
    PurchasingCase,
    SupplierAvailabilitySnapshot,
    SupplierTerm,
)
from app.purchasing_tools import (
    REQUIRED_TOOL_NAMES,
    TOOL_REGISTRY,
    get_case_context,
)
from app.services.simulator import simulate_create_purchase_order


def collect_current_evidence(
    session,
    case_id: UUID,
) -> tuple[CaseContext, dict[str, dict]]:
    context = get_case_context(session, case_id)
    evidence = {
        name: TOOL_REGISTRY[name](session, case_id).model_dump(mode="json")
        for name in REQUIRED_TOOL_NAMES
    }
    return context, evidence


def replan_result(
    *,
    session,
    run_id: UUID,
    idempotency_key: str,
    requested_quantity: int,
    reason_code: str,
) -> ActionResult:
    session.add(
        ActionAttempt(
            run_id=run_id,
            purchase_order_id=None,
            idempotency_key=idempotency_key,
            action_type="create",
            requested_quantity=requested_quantity,
            actual_quantity=None,
            status="replan_required",
            response_payload={"accepted": False, "reason_code": reason_code},
        )
    )
    return ActionResult(
        status="replan_required",
        action_type="none",
        idempotency_key=idempotency_key,
        purchase_order_id=None,
        requested_quantity=requested_quantity,
        reported_quantity=None,
        reason_code=reason_code,
    )


def make_idempotency_key(case_id: UUID, quantity: int, evidence: dict[str, dict]) -> str:
    evidence_version = json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
    )
    material = f"{case_id}:create:{quantity}:{evidence_version}"
    return sha256(material.encode("utf-8")).hexdigest()


def execute_purchase(
    run_id: UUID,
    case_id: UUID,
    requested_quantity: int,
    idempotency_key: str,
) -> ActionResult:
    with session_scope() as session:
        purchasing_case = session.scalar(
            select(PurchasingCase)
            .where(PurchasingCase.id == case_id)
            .with_for_update()
        )
        if purchasing_case is None:
            return ActionResult(
                status="replan_required",
                action_type="none",
                idempotency_key=None,
                purchase_order_id=None,
                requested_quantity=requested_quantity,
                reported_quantity=None,
                reason_code="case_not_found",
            )

        existing_order = session.scalar(
            select(PurchaseOrder).where(PurchaseOrder.idempotency_key == idempotency_key)
        )
        if existing_order is not None:
            session.add(
                ActionAttempt(
                    run_id=run_id,
                    purchase_order_id=existing_order.id,
                    idempotency_key=idempotency_key,
                    action_type="create",
                    requested_quantity=requested_quantity,
                    actual_quantity=existing_order.quantity,
                    status="idempotent_replay",
                    response_payload={"accepted": True, "reported_quantity": existing_order.quantity},
                )
            )
            return ActionResult(
                status="idempotent_replay",
                action_type="create",
                idempotency_key=idempotency_key,
                purchase_order_id=str(existing_order.id),
                requested_quantity=requested_quantity,
                reported_quantity=existing_order.quantity,
            )

        budget = session.scalar(
            select(BudgetSnapshot)
            .where(BudgetSnapshot.case_id == case_id)
            .with_for_update()
        )
        capacity = session.scalar(
            select(CapacitySnapshot)
            .where(CapacitySnapshot.case_id == case_id)
            .with_for_update()
        )
        supplier_term = session.scalar(
            select(SupplierTerm)
            .where(
                SupplierTerm.supplier_id == purchasing_case.supplier_id,
                SupplierTerm.product_id == purchasing_case.product_id,
            )
            .with_for_update()
        )
        availability = session.scalar(
            select(SupplierAvailabilitySnapshot)
            .where(SupplierAvailabilitySnapshot.case_id == case_id)
            .with_for_update()
        )
        if any(
            item is None
            for item in (budget, capacity, supplier_term, availability)
        ):
            return replan_result(
                session=session,
                run_id=run_id,
                idempotency_key=idempotency_key,
                requested_quantity=requested_quantity,
                reason_code="constraint_evidence_missing",
            )

        context, evidence = collect_current_evidence(session, case_id)
        assessment = assess_evidence(context=context, evidence=evidence)
        if not assessment.complete:
            return replan_result(
                session=session,
                run_id=run_id,
                idempotency_key=idempotency_key,
                requested_quantity=requested_quantity,
                reason_code="evidence_missing_or_stale",
            )

        supplier = SupplierEvidence.model_validate(evidence["get_supplier_terms"])
        analysis = analyze_purchase(
            context=context,
            inventory=InventoryEvidence.model_validate(evidence["get_inventory"]),
            forecast=ForecastEvidence.model_validate(evidence["get_demand_forecast"]),
            open_orders=OpenOrdersEvidence.model_validate(
                evidence["get_open_purchase_orders"]
            ),
            supplier=supplier,
            budget=BudgetEvidence.model_validate(evidence["get_budget"]),
            capacity=CapacityEvidence.model_validate(evidence["get_storage_capacity"]),
        )
        selected = next(
            (
                candidate
                for candidate in analysis.candidates
                if candidate.id == analysis.policy_candidate_id
            ),
            None,
        )
        if (
            selected is None
            or not selected.feasible
            or selected.quantity != requested_quantity
            or selected.arrival_date is None
        ):
            return replan_result(
                session=session,
                run_id=run_id,
                idempotency_key=idempotency_key,
                requested_quantity=requested_quantity,
                reason_code="authorized_action_no_longer_valid",
            )

        simulated = simulate_create_purchase_order(
            mode=purchasing_case.simulator_mode,
            requested_quantity=requested_quantity,
            case_pack_quantity=supplier.case_pack_quantity,
        )
        actual_quantity = simulated.persisted_quantity

        now = datetime.now(UTC)
        purchase_order = PurchaseOrder(
            id=uuid4(),
            case_id=case_id,
            product_id=purchasing_case.product_id,
            node_id=purchasing_case.node_id,
            supplier_id=purchasing_case.supplier_id,
            quantity=actual_quantity,
            unit_cost_minor=supplier.unit_cost_minor,
            currency=supplier.currency,
            status="confirmed",
            expected_delivery_date=selected.arrival_date,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        session.add(purchase_order)
        session.flush()

        budget.available_minor -= actual_quantity * supplier.unit_cost_minor
        budget.observed_at = now
        capacity.available_quantity -= actual_quantity
        capacity.observed_at = now
        availability.available_quantity -= actual_quantity
        availability.observed_at = now

        session.add(
            ActionAttempt(
                run_id=run_id,
                purchase_order_id=purchase_order.id,
                idempotency_key=idempotency_key,
                action_type="create",
                requested_quantity=requested_quantity,
                actual_quantity=actual_quantity,
                status="acknowledged",
                    response_payload={
                        "accepted": simulated.accepted,
                        "reported_quantity": simulated.reported_quantity,
                    },
            )
        )
        return ActionResult(
            status="acknowledged",
            action_type="create",
            idempotency_key=idempotency_key,
            purchase_order_id=str(purchase_order.id),
            requested_quantity=requested_quantity,
            reported_quantity=simulated.reported_quantity,
        )
