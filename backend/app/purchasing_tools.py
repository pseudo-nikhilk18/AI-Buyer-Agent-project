from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.schemas import (
    BudgetEvidence,
    CapacityEvidence,
    CaseContext,
    ForecastEvidence,
    ForecastPoint,
    InventoryEvidence,
    OpenOrdersEvidence,
    OpenPurchaseOrderEvidence,
    SupplierEvidence,
)
from app.models import (
    BudgetSnapshot,
    CapacitySnapshot,
    DemandForecast,
    InventorySnapshot,
    PurchaseOrder,
    PurchasingCase,
    SupplierAvailabilitySnapshot,
    SupplierTerm,
)

REQUIRED_TOOL_NAMES = [
    "get_inventory",
    "get_demand_forecast",
    "get_open_purchase_orders",
    "get_supplier_terms",
    "get_budget",
    "get_storage_capacity",
]

TOOL_DESCRIPTIONS = {
    "get_inventory": "Current on-hand, reserved, and damaged inventory at the fulfillment node.",
    "get_demand_forecast": "Daily expected demand across the replenishment planning horizon.",
    "get_open_purchase_orders": "Existing inbound supply and its expected arrival date.",
    "get_supplier_terms": "Lead time, MOQ, case pack, price, availability, approval, and reliability.",
    "get_budget": "Purchasing budget still available for this case.",
    "get_storage_capacity": "Remaining inbound storage capacity for this product at the node.",
}


class EvidenceNotFoundError(RuntimeError):
    pass


def get_case_context(session: Session, case_id: UUID) -> CaseContext:
    purchasing_case = session.scalar(
        select(PurchasingCase).where(PurchasingCase.id == case_id)
    )
    if purchasing_case is None:
        raise EvidenceNotFoundError("Purchasing case was not found.")

    return CaseContext(
        case_id=str(purchasing_case.id),
        code=purchasing_case.code,
        title=purchasing_case.title,
        scenario_type=purchasing_case.scenario_type,
        product_id=str(purchasing_case.product_id),
        product_name=purchasing_case.product.name,
        sku=purchasing_case.product.sku,
        node_id=str(purchasing_case.node_id),
        node_name=purchasing_case.node.name,
        supplier_id=str(purchasing_case.supplier_id),
        recommended_quantity=purchasing_case.recommended_quantity,
        simulator_mode=purchasing_case.simulator_mode,
        review_period_days=purchasing_case.policy.review_period_days,
        safety_stock_days=purchasing_case.policy.safety_stock_days,
        inventory_freshness_minutes=purchasing_case.policy.inventory_freshness_minutes,
        forecast_freshness_hours=purchasing_case.policy.forecast_freshness_hours,
        supplier_freshness_minutes=purchasing_case.policy.supplier_freshness_minutes,
        constraint_freshness_minutes=purchasing_case.policy.constraint_freshness_minutes,
        auto_spend_limit_minor=purchasing_case.policy.auto_spend_limit_minor,
    )


def get_inventory(session: Session, case_id: UUID) -> InventoryEvidence:
    snapshot = session.scalar(
        select(InventorySnapshot)
        .where(InventorySnapshot.case_id == case_id)
        .order_by(InventorySnapshot.observed_at.desc())
        .limit(1)
    )
    if snapshot is None:
        raise EvidenceNotFoundError("Inventory evidence was not found.")
    return InventoryEvidence.model_validate(snapshot, from_attributes=True)


def get_demand_forecast(session: Session, case_id: UUID) -> ForecastEvidence:
    rows = session.scalars(
        select(DemandForecast)
        .where(DemandForecast.case_id == case_id)
        .order_by(DemandForecast.demand_date)
    ).all()
    if not rows:
        raise EvidenceNotFoundError("Demand forecast evidence was not found.")
    return ForecastEvidence(
        points=[ForecastPoint.model_validate(row, from_attributes=True) for row in rows],
        observed_at=max(row.observed_at for row in rows),
    )


def get_open_purchase_orders(session: Session, case_id: UUID) -> OpenOrdersEvidence:
    rows = session.scalars(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.case_id == case_id,
            PurchaseOrder.status.in_(["open", "confirmed"]),
        )
        .order_by(PurchaseOrder.expected_delivery_date)
    ).all()
    return OpenOrdersEvidence(
        orders=[
            OpenPurchaseOrderEvidence(
                id=str(row.id),
                quantity=row.quantity,
                expected_delivery_date=row.expected_delivery_date,
                status=row.status,
            )
            for row in rows
        ],
        observed_at=max((row.updated_at for row in rows), default=datetime.now(UTC)),
    )


def get_supplier_terms(session: Session, case_id: UUID) -> SupplierEvidence:
    purchasing_case = session.get(PurchasingCase, case_id)
    if purchasing_case is None:
        raise EvidenceNotFoundError("Purchasing case was not found.")
    term = session.scalar(
        select(SupplierTerm).where(
            SupplierTerm.supplier_id == purchasing_case.supplier_id,
            SupplierTerm.product_id == purchasing_case.product_id,
        )
    )
    if term is None:
        raise EvidenceNotFoundError("Supplier terms were not found.")
    availability = session.scalar(
        select(SupplierAvailabilitySnapshot).where(
            SupplierAvailabilitySnapshot.case_id == case_id
        )
    )
    if availability is None:
        raise EvidenceNotFoundError("Supplier availability was not found.")
    return SupplierEvidence(
        supplier_id=str(term.supplier_id),
        supplier_name=term.supplier.name,
        active=term.supplier.active,
        approved=term.supplier.approved,
        reliability_percent=term.supplier.reliability_percent,
        unit_cost_minor=term.unit_cost_minor,
        currency=term.currency,
        minimum_order_quantity=term.minimum_order_quantity,
        case_pack_quantity=term.case_pack_quantity,
        lead_time_days=term.lead_time_days,
        available_quantity=availability.available_quantity,
        observed_at=min(term.observed_at, availability.observed_at),
    )


def get_budget(session: Session, case_id: UUID) -> BudgetEvidence:
    snapshot = session.scalar(select(BudgetSnapshot).where(BudgetSnapshot.case_id == case_id))
    if snapshot is None:
        raise EvidenceNotFoundError("Budget evidence was not found.")
    return BudgetEvidence.model_validate(snapshot, from_attributes=True)


def get_storage_capacity(session: Session, case_id: UUID) -> CapacityEvidence:
    snapshot = session.scalar(
        select(CapacitySnapshot).where(CapacitySnapshot.case_id == case_id)
    )
    if snapshot is None:
        raise EvidenceNotFoundError("Storage-capacity evidence was not found.")
    return CapacityEvidence.model_validate(snapshot, from_attributes=True)


ToolFunction = Callable[[Session, UUID], object]

TOOL_REGISTRY: dict[str, ToolFunction] = {
    "get_inventory": get_inventory,
    "get_demand_forecast": get_demand_forecast,
    "get_open_purchase_orders": get_open_purchase_orders,
    "get_supplier_terms": get_supplier_terms,
    "get_budget": get_budget,
    "get_storage_capacity": get_storage_capacity,
}
