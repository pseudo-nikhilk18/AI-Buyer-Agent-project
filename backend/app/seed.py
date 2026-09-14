from datetime import UTC, datetime, timedelta
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import session_scope
from app.evals.dataset import EvaluationExample, load_evaluation_dataset
from app.models import (
    BudgetSnapshot,
    CapacitySnapshot,
    DemandForecast,
    FulfillmentNode,
    InventorySnapshot,
    Product,
    PurchaseOrder,
    PurchasingCase,
    PurchasingPolicy,
    Supplier,
    SupplierAvailabilitySnapshot,
    SupplierTerm,
)


def stable_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"buyer-agent-demo:{name}")


def _upsert_shared_records(
    session: Session,
    example: EvaluationExample,
    now: datetime,
) -> tuple[UUID, UUID, UUID, UUID]:
    case_input = example.input

    product_id = stable_id(f"product-{case_input.product.sku.lower()}")
    product = session.scalar(select(Product).where(Product.sku == case_input.product.sku))
    if product is None:
        product = Product(id=product_id, sku=case_input.product.sku)
        session.add(product)
    product.name = case_input.product.name
    product.active = True

    node_id = stable_id(f"node-{case_input.node.code.lower()}")
    node = session.scalar(
        select(FulfillmentNode).where(FulfillmentNode.code == case_input.node.code)
    )
    if node is None:
        node = FulfillmentNode(id=node_id, code=case_input.node.code)
        session.add(node)
    node.name = case_input.node.name
    node.active = True

    supplier_id = stable_id(f"supplier-{case_input.supplier.code.lower()}")
    supplier = session.scalar(
        select(Supplier).where(Supplier.code == case_input.supplier.code)
    )
    if supplier is None:
        supplier = Supplier(id=supplier_id, code=case_input.supplier.code)
        session.add(supplier)
    supplier.name = case_input.supplier.name
    supplier.active = case_input.supplier.active
    supplier.approved = case_input.supplier.approved
    supplier.reliability_percent = case_input.supplier.reliability_percent

    policy_id = stable_id(f"policy-{case_input.policy.code.lower()}")
    policy = session.scalar(
        select(PurchasingPolicy).where(PurchasingPolicy.code == case_input.policy.code)
    )
    if policy is None:
        policy = PurchasingPolicy(id=policy_id, code=case_input.policy.code)
        session.add(policy)
    policy.review_period_days = case_input.policy.review_period_days
    policy.safety_stock_days = case_input.policy.safety_stock_days
    policy.inventory_freshness_minutes = case_input.policy.inventory_freshness_minutes
    policy.forecast_freshness_hours = case_input.policy.forecast_freshness_hours
    policy.supplier_freshness_minutes = case_input.policy.supplier_freshness_minutes
    policy.constraint_freshness_minutes = case_input.policy.constraint_freshness_minutes
    policy.auto_spend_limit_minor = case_input.policy.auto_spend_limit_minor

    session.flush()
    term = session.scalar(
        select(SupplierTerm).where(
            SupplierTerm.supplier_id == supplier.id,
            SupplierTerm.product_id == product.id,
        )
    )
    if term is None:
        term = SupplierTerm(
            id=stable_id(
                f"supplier-term-{case_input.supplier.code.lower()}-"
                f"{case_input.product.sku.lower()}"
            ),
            supplier_id=supplier.id,
            product_id=product.id,
        )
        session.add(term)
    term.unit_cost_minor = case_input.supplier_terms.unit_cost_minor
    term.currency = case_input.supplier_terms.currency
    term.minimum_order_quantity = case_input.supplier_terms.minimum_order_quantity
    term.case_pack_quantity = case_input.supplier_terms.case_pack_quantity
    term.lead_time_days = case_input.supplier_terms.lead_time_days
    term.observed_at = now - timedelta(minutes=5)

    return product.id, node.id, supplier.id, policy.id


def seed_demo_data(session: Session) -> list[UUID]:
    """Seed agent inputs from the versioned evaluation dataset, never its references."""
    dataset = load_evaluation_dataset()
    now = datetime.now(UTC)
    case_codes = [item.case_code for item in dataset.examples]
    session.execute(delete(PurchasingCase).where(PurchasingCase.code.in_(case_codes)))

    created_ids: list[UUID] = []
    for index, example in enumerate(dataset.examples):
        case_input = example.input
        product_id, node_id, supplier_id, policy_id = _upsert_shared_records(
            session, example, now
        )
        case_id = stable_id(f"case-{example.case_code.lower()}")
        created_ids.append(case_id)
        session.add(
            PurchasingCase(
                id=case_id,
                code=example.case_code,
                title=case_input.title,
                scenario_type=case_input.scenario_type,
                product_id=product_id,
                node_id=node_id,
                supplier_id=supplier_id,
                policy_id=policy_id,
                recommended_quantity=case_input.recommended_quantity,
                status="ready",
                simulator_mode=case_input.simulator_mode,
                created_at=now + timedelta(seconds=index),
            )
        )
        session.flush()

        operational_observed_at = now - timedelta(minutes=5)
        forecast_observed_at = now - timedelta(hours=case_input.forecast.age_hours)
        omitted = set(case_input.omitted_evidence)

        if "get_inventory" not in omitted:
            session.add(
                InventorySnapshot(
                    id=stable_id(f"inventory-{example.case_code}"),
                    case_id=case_id,
                    **case_input.inventory.model_dump(),
                    observed_at=operational_observed_at,
                )
            )
        if "get_demand_forecast" not in omitted:
            for day_offset in range(1, case_input.forecast.days + 1):
                session.add(
                    DemandForecast(
                        id=stable_id(f"forecast-{example.case_code}-{day_offset}"),
                        case_id=case_id,
                        demand_date=now.date() + timedelta(days=day_offset),
                        quantity=case_input.forecast.daily_quantity,
                        observed_at=forecast_observed_at,
                    )
                )
        if "get_budget" not in omitted:
            session.add(
                BudgetSnapshot(
                    id=stable_id(f"budget-{example.case_code}"),
                    case_id=case_id,
                    available_minor=case_input.budget_minor,
                    currency=case_input.supplier_terms.currency,
                    observed_at=operational_observed_at,
                )
            )
        if "get_storage_capacity" not in omitted:
            session.add(
                CapacitySnapshot(
                    id=stable_id(f"capacity-{example.case_code}"),
                    case_id=case_id,
                    available_quantity=case_input.storage_capacity_quantity,
                    observed_at=operational_observed_at,
                )
            )
        if "get_supplier_terms" not in omitted:
            session.add(
                SupplierAvailabilitySnapshot(
                    id=stable_id(f"supplier-availability-{example.case_code}"),
                    case_id=case_id,
                    available_quantity=case_input.supplier_available_quantity,
                    observed_at=operational_observed_at,
                )
            )
        if "get_open_purchase_orders" not in omitted and case_input.inbound_order:
            session.add(
                PurchaseOrder(
                    id=stable_id(f"inbound-po-{example.case_code}"),
                    case_id=case_id,
                    product_id=product_id,
                    node_id=node_id,
                    supplier_id=supplier_id,
                    quantity=case_input.inbound_order.quantity,
                    unit_cost_minor=case_input.supplier_terms.unit_cost_minor,
                    currency=case_input.supplier_terms.currency,
                    status=case_input.inbound_order.status,
                    expected_delivery_date=(
                        now.date() + timedelta(days=case_input.inbound_order.arrival_days)
                    ),
                    idempotency_key=None,
                    created_at=now - timedelta(days=1),
                    updated_at=operational_observed_at,
                )
            )

    return created_ids


def main() -> None:
    with session_scope() as session:
        case_ids = seed_demo_data(session)
    print(f"Seeded {len(case_ids)} purchasing evaluation cases.")


if __name__ == "__main__":
    main()
