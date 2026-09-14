from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import session_scope
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


PRODUCT_ID = stable_id("product-rice-1kg")
NODE_ID = stable_id("node-north-hub")
SUPPLIER_ID = stable_id("supplier-harvest")
SUPPLIER_TERM_ID = stable_id("supplier-term-harvest-rice")
POLICY_ID = stable_id("policy-standard")


@dataclass(frozen=True)
class CaseSeed:
    code: str
    title: str
    recommended_quantity: int
    daily_demand: int
    on_hand_quantity: int = 400
    reserved_quantity: int = 50
    damaged_quantity: int = 10
    budget_minor: int = 7_000_000
    storage_capacity_quantity: int = 700
    supplier_available_quantity: int = 5_000
    inbound_quantity: int = 120
    scenario_type: str = "recommendation_review"
    stale_forecast: bool = False
    simulator_mode: str = "normal"


CASE_SEEDS = (
    CaseSeed(
        code="REC-ACCEPT",
        title="Recommendation matches the safe quantity",
        recommended_quantity=650,
        daily_demand=90,
    ),
    CaseSeed(
        code="REC-MODIFY",
        title="Recommendation carries avoidable excess stock",
        recommended_quantity=800,
        daily_demand=90,
    ),
    CaseSeed(
        code="REC-REJECT",
        title="Existing coverage makes another order unnecessary",
        recommended_quantity=800,
        daily_demand=90,
        on_hand_quantity=1_200,
    ),
    CaseSeed(
        code="REC-INVESTIGATE",
        title="The demand forecast is too old to authorize spending",
        recommended_quantity=800,
        daily_demand=90,
        stale_forecast=True,
    ),
    CaseSeed(
        code="REC-VALIDATE",
        title="The purchasing system persists the wrong quantity",
        recommended_quantity=650,
        daily_demand=90,
        simulator_mode="persist_short",
    ),
    CaseSeed(
        code="REC-REVIEW",
        title="A safe order exceeds automatic spending authority",
        recommended_quantity=800,
        daily_demand=105,
        budget_minor=10_000_000,
        storage_capacity_quantity=900,
    ),
    CaseSeed(
        code="SUPPLIER-SHORTFALL",
        title="Confirmed supply covers only part of the requirement",
        recommended_quantity=500,
        daily_demand=90,
        inbound_quantity=250,
        supplier_available_quantity=250,
        scenario_type="supplier_shortfall",
    ),
    CaseSeed(
        code="DEMAND-CHANGE",
        title="Higher demand changes the safe order quantity",
        recommended_quantity=650,
        daily_demand=100,
        storage_capacity_quantity=800,
        scenario_type="demand_change",
    ),
    CaseSeed(
        code="HARD-CONSTRAINT",
        title="Available budget blocks the required purchase",
        recommended_quantity=650,
        daily_demand=90,
        budget_minor=5_000_000,
        scenario_type="constraint_resolution",
    ),
)


def upsert_shared_records(session: Session, now: datetime) -> None:
    product = session.get(Product, PRODUCT_ID)
    if product is None:
        product = Product(id=PRODUCT_ID, sku="RICE-1KG", name="Everyday Basmati Rice · 1 kg")
        session.add(product)
    else:
        product.sku = "RICE-1KG"
        product.name = "Everyday Basmati Rice · 1 kg"
        product.active = True

    node = session.get(FulfillmentNode, NODE_ID)
    if node is None:
        node = FulfillmentNode(id=NODE_ID, code="NORTH-HUB", name="North fulfillment hub")
        session.add(node)
    else:
        node.name = "North fulfillment hub"
        node.active = True

    supplier = session.get(Supplier, SUPPLIER_ID)
    if supplier is None:
        supplier = Supplier(
            id=SUPPLIER_ID,
            code="HARVEST",
            name="Harvest Supply Co.",
            active=True,
            approved=True,
            reliability_percent=96,
        )
        session.add(supplier)
    else:
        supplier.name = "Harvest Supply Co."
        supplier.active = True
        supplier.approved = True
        supplier.reliability_percent = 96

    policy = session.get(PurchasingPolicy, POLICY_ID)
    if policy is None:
        policy = PurchasingPolicy(id=POLICY_ID, code="STANDARD")
        session.add(policy)
    policy.review_period_days = 7
    policy.safety_stock_days = 2
    policy.inventory_freshness_minutes = 15
    policy.forecast_freshness_hours = 24
    policy.supplier_freshness_minutes = 60
    policy.constraint_freshness_minutes = 15
    policy.auto_spend_limit_minor = 6_000_000

    session.flush()
    term = session.get(SupplierTerm, SUPPLIER_TERM_ID)
    if term is None:
        term = SupplierTerm(
            id=SUPPLIER_TERM_ID,
            supplier_id=SUPPLIER_ID,
            product_id=PRODUCT_ID,
        )
        session.add(term)
    term.unit_cost_minor = 8_000
    term.currency = "INR"
    term.minimum_order_quantity = 100
    term.case_pack_quantity = 50
    term.lead_time_days = 3
    term.observed_at = now - timedelta(minutes=5)


def seed_demo_data(session: Session) -> list[UUID]:
    now = datetime.now(UTC)
    case_codes = [item.code for item in CASE_SEEDS]
    session.execute(delete(PurchasingCase).where(PurchasingCase.code.in_(case_codes)))
    upsert_shared_records(session, now)

    created_ids: list[UUID] = []
    for index, item in enumerate(CASE_SEEDS):
        case_id = stable_id(f"case-{item.code.lower()}")
        created_ids.append(case_id)
        purchasing_case = PurchasingCase(
            id=case_id,
            code=item.code,
            title=item.title,
            scenario_type=item.scenario_type,
            product_id=PRODUCT_ID,
            node_id=NODE_ID,
            supplier_id=SUPPLIER_ID,
            policy_id=POLICY_ID,
            recommended_quantity=item.recommended_quantity,
            status="ready",
            simulator_mode=item.simulator_mode,
            created_at=now + timedelta(seconds=index),
        )
        session.add(purchasing_case)
        session.flush()

        operational_observed_at = now - timedelta(minutes=5)
        forecast_observed_at = (
            now - timedelta(hours=48) if item.stale_forecast else operational_observed_at
        )
        session.add(
            InventorySnapshot(
                id=stable_id(f"inventory-{item.code}"),
                case_id=case_id,
                on_hand_quantity=item.on_hand_quantity,
                reserved_quantity=item.reserved_quantity,
                damaged_quantity=item.damaged_quantity,
                observed_at=operational_observed_at,
            )
        )
        for day_offset in range(1, 11):
            session.add(
                DemandForecast(
                    id=stable_id(f"forecast-{item.code}-{day_offset}"),
                    case_id=case_id,
                    demand_date=now.date() + timedelta(days=day_offset),
                    quantity=item.daily_demand,
                    observed_at=forecast_observed_at,
                )
            )
        session.add_all(
            [
                BudgetSnapshot(
                    id=stable_id(f"budget-{item.code}"),
                    case_id=case_id,
                    available_minor=item.budget_minor,
                    currency="INR",
                    observed_at=operational_observed_at,
                ),
                CapacitySnapshot(
                    id=stable_id(f"capacity-{item.code}"),
                    case_id=case_id,
                    available_quantity=item.storage_capacity_quantity,
                    observed_at=operational_observed_at,
                ),
                SupplierAvailabilitySnapshot(
                    id=stable_id(f"supplier-availability-{item.code}"),
                    case_id=case_id,
                    available_quantity=item.supplier_available_quantity,
                    observed_at=operational_observed_at,
                ),
                PurchaseOrder(
                    id=stable_id(f"inbound-po-{item.code}"),
                    case_id=case_id,
                    product_id=PRODUCT_ID,
                    node_id=NODE_ID,
                    supplier_id=SUPPLIER_ID,
                    quantity=item.inbound_quantity,
                    unit_cost_minor=8_000,
                    currency="INR",
                    status="confirmed",
                    expected_delivery_date=now.date() + timedelta(days=2),
                    idempotency_key=None,
                    created_at=now - timedelta(days=1),
                    updated_at=operational_observed_at,
                ),
            ]
        )

    return created_ids


def main() -> None:
    with session_scope() as session:
        case_ids = seed_demo_data(session)
    print(f"Seeded {len(case_ids)} purchasing cases.")


if __name__ == "__main__":
    main()
