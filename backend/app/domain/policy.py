from collections import defaultdict
from datetime import date, timedelta
from math import ceil

from app.domain.schemas import (
    BudgetEvidence,
    CapacityEvidence,
    CaseContext,
    ForecastEvidence,
    InventoryEvidence,
    OpenOrdersEvidence,
    PolicyCheckResult,
    ProjectionPoint,
    PurchaseCandidate,
    PurchasingAnalysis,
    SupplierEvidence,
)


def round_to_pack(quantity: int, minimum: int, pack: int) -> int:
    if quantity <= 0:
        return 0
    return max(minimum, ceil(quantity / pack) * pack)


def simulate_inventory(
    *,
    initial_quantity: int,
    forecast: ForecastEvidence,
    open_orders: OpenOrdersEvidence,
    candidate_quantity: int,
    candidate_arrival_date: date | None,
) -> list[ProjectionPoint]:
    incoming_by_date: dict[date, int] = defaultdict(int)
    for order in open_orders.orders:
        if order.status in {"open", "confirmed"}:
            incoming_by_date[order.expected_delivery_date] += order.quantity
    if candidate_quantity and candidate_arrival_date is not None:
        incoming_by_date[candidate_arrival_date] += candidate_quantity

    running_quantity = initial_quantity
    projection: list[ProjectionPoint] = []
    for point in sorted(forecast.points, key=lambda item: item.demand_date):
        opening_quantity = running_quantity
        incoming_quantity = incoming_by_date[point.demand_date]
        running_quantity += incoming_quantity - point.quantity
        projection.append(
            ProjectionPoint(
                date=point.demand_date,
                opening_quantity=opening_quantity,
                incoming_quantity=incoming_quantity,
                demand_quantity=point.quantity,
                closing_quantity=running_quantity,
            )
        )
    return projection


def build_candidate(
    *,
    candidate_id: str,
    quantity: int,
    arrival_date: date | None,
    initial_quantity: int,
    forecast: ForecastEvidence,
    open_orders: OpenOrdersEvidence,
    supplier: SupplierEvidence,
    budget: BudgetEvidence,
    capacity: CapacityEvidence,
    safety_stock_quantity: int,
) -> PurchaseCandidate:
    projection = simulate_inventory(
        initial_quantity=initial_quantity,
        forecast=forecast,
        open_orders=open_orders,
        candidate_quantity=quantity,
        candidate_arrival_date=arrival_date,
    )
    ending_quantity = projection[-1].closing_quantity
    minimum_quantity = min(point.closing_quantity for point in projection)
    violations: list[str] = []

    if minimum_quantity < 0:
        violations.append("delivery_too_late")
    if ending_quantity < safety_stock_quantity:
        violations.append("safety_stock_not_met")

    if quantity > 0:
        if quantity < supplier.minimum_order_quantity:
            violations.append("below_minimum_order_quantity")
        if quantity % supplier.case_pack_quantity != 0:
            violations.append("not_case_pack_multiple")
        if quantity > supplier.available_quantity:
            violations.append("supplier_availability_exceeded")
        if quantity * supplier.unit_cost_minor > budget.available_minor:
            violations.append("budget_exceeded")
        if quantity > capacity.available_quantity:
            violations.append("storage_capacity_exceeded")
        if not supplier.active:
            violations.append("supplier_inactive")
    return PurchaseCandidate(
        id=candidate_id,
        quantity=quantity,
        arrival_date=arrival_date,
        spend_minor=quantity * supplier.unit_cost_minor,
        currency=supplier.currency,
        projected_ending_quantity=ending_quantity,
        projected_minimum_quantity=minimum_quantity,
        safety_stock_quantity=safety_stock_quantity,
        surplus_above_safety=max(0, ending_quantity - safety_stock_quantity),
        shortfall_below_safety=max(0, safety_stock_quantity - ending_quantity),
        feasible=not violations,
        violations=violations,
        projection=projection,
    )


def analyze_purchase(
    *,
    context: CaseContext,
    inventory: InventoryEvidence,
    forecast: ForecastEvidence,
    open_orders: OpenOrdersEvidence,
    supplier: SupplierEvidence,
    budget: BudgetEvidence,
    capacity: CapacityEvidence,
) -> PurchasingAnalysis:
    planning_horizon_days = supplier.lead_time_days + context.review_period_days
    horizon_forecast = ForecastEvidence(
        points=sorted(forecast.points, key=lambda item: item.demand_date)[:planning_horizon_days],
        observed_at=forecast.observed_at,
    )
    usable_inventory = max(
        0,
        inventory.on_hand_quantity
        - inventory.reserved_quantity
        - inventory.damaged_quantity,
    )
    forecast_quantity = sum(point.quantity for point in horizon_forecast.points)
    average_daily_demand = ceil(forecast_quantity / planning_horizon_days)
    safety_stock_quantity = average_daily_demand * context.safety_stock_days
    baseline_projection = simulate_inventory(
        initial_quantity=usable_inventory,
        forecast=horizon_forecast,
        open_orders=open_orders,
        candidate_quantity=0,
        candidate_arrival_date=None,
    )
    baseline_ending = baseline_projection[-1].closing_quantity
    net_requirement = max(0, safety_stock_quantity - baseline_ending)
    calculated_order = round_to_pack(
        net_requirement,
        supplier.minimum_order_quantity,
        supplier.case_pack_quantity,
    )
    arrival_date = horizon_forecast.points[0].demand_date + timedelta(
        days=max(0, supplier.lead_time_days - 1)
    )

    no_action = build_candidate(
        candidate_id="no_action",
        quantity=0,
        arrival_date=None,
        initial_quantity=usable_inventory,
        forecast=horizon_forecast,
        open_orders=open_orders,
        supplier=supplier,
        budget=budget,
        capacity=capacity,
        safety_stock_quantity=safety_stock_quantity,
    )
    original = build_candidate(
        candidate_id="original_recommendation",
        quantity=context.recommended_quantity,
        arrival_date=arrival_date,
        initial_quantity=usable_inventory,
        forecast=horizon_forecast,
        open_orders=open_orders,
        supplier=supplier,
        budget=budget,
        capacity=capacity,
        safety_stock_quantity=safety_stock_quantity,
    )
    calculated = build_candidate(
        candidate_id="calculated_order",
        quantity=calculated_order,
        arrival_date=arrival_date if calculated_order else None,
        initial_quantity=usable_inventory,
        forecast=horizon_forecast,
        open_orders=open_orders,
        supplier=supplier,
        budget=budget,
        capacity=capacity,
        safety_stock_quantity=safety_stock_quantity,
    )

    if calculated_order == 0:
        policy_decision = "reject"
        policy_candidate_id = "no_action"
        reason_codes = ["inventory_coverage_sufficient"]
        selected = no_action
    elif not calculated.feasible:
        policy_decision = "investigate"
        policy_candidate_id = None
        reason_codes = ["calculated_order_blocked", *calculated.violations]
        selected = calculated
    elif context.recommended_quantity == calculated_order and original.feasible:
        policy_decision = "accept"
        policy_candidate_id = "original_recommendation"
        reason_codes = ["recommendation_matches_safe_quantity"]
        selected = original
    else:
        policy_decision = "modify"
        policy_candidate_id = "calculated_order"
        reason_codes = ["recommendation_differs_from_safe_quantity"]
        selected = calculated

    checks = build_policy_checks(
        context=context,
        supplier=supplier,
        budget=budget,
        capacity=capacity,
        selected=selected,
    )
    return PurchasingAnalysis(
        planning_horizon_days=planning_horizon_days,
        usable_inventory_quantity=usable_inventory,
        forecast_quantity=forecast_quantity,
        safety_stock_quantity=safety_stock_quantity,
        net_requirement_quantity=net_requirement,
        calculated_order_quantity=calculated_order,
        policy_decision=policy_decision,
        policy_candidate_id=policy_candidate_id,
        candidates=[no_action, original, calculated],
        policy_checks=checks,
        reason_codes=reason_codes,
    )


def build_policy_checks(
    *,
    context: CaseContext,
    supplier: SupplierEvidence,
    budget: BudgetEvidence,
    capacity: CapacityEvidence,
    selected: PurchaseCandidate,
) -> list[PolicyCheckResult]:
    if selected.quantity == 0:
        return [
            PolicyCheckResult(
                code="NO_PURCHASE_REQUIRED",
                passed=True,
                severity="information",
                detail="Current and incoming inventory already protect the planning horizon.",
            )
        ]

    spend = selected.quantity * supplier.unit_cost_minor
    return [
        PolicyCheckResult(
            code="SUPPLIER_ACTIVE",
            passed=supplier.active,
            severity="hard",
            detail="The selected supplier must be active.",
            actual=str(supplier.active).lower(),
            expected="true",
        ),
        PolicyCheckResult(
            code="MINIMUM_ORDER",
            passed=selected.quantity >= supplier.minimum_order_quantity,
            severity="hard",
            detail="The quantity must meet the supplier minimum.",
            actual=selected.quantity,
            expected=supplier.minimum_order_quantity,
        ),
        PolicyCheckResult(
            code="CASE_PACK",
            passed=selected.quantity % supplier.case_pack_quantity == 0,
            severity="hard",
            detail="The quantity must be a complete supplier case pack.",
            actual=selected.quantity,
            expected={"multiple_of": supplier.case_pack_quantity},
        ),
        PolicyCheckResult(
            code="SUPPLIER_AVAILABILITY",
            passed=selected.quantity <= supplier.available_quantity,
            severity="hard",
            detail="The quantity cannot exceed confirmed supplier availability.",
            actual=selected.quantity,
            expected={"maximum": supplier.available_quantity},
        ),
        PolicyCheckResult(
            code="BUDGET",
            passed=spend <= budget.available_minor,
            severity="hard",
            detail="The purchase must fit within the available budget.",
            actual=spend,
            expected={"maximum": budget.available_minor},
        ),
        PolicyCheckResult(
            code="STORAGE_CAPACITY",
            passed=selected.quantity <= capacity.available_quantity,
            severity="hard",
            detail="The arriving quantity must fit within available storage capacity.",
            actual=selected.quantity,
            expected={"maximum": capacity.available_quantity},
        ),
        PolicyCheckResult(
            code="DELIVERY_TIMING",
            passed=selected.projected_minimum_quantity >= 0,
            severity="hard",
            detail="Projected inventory must not become negative before delivery.",
            actual=selected.projected_minimum_quantity,
            expected={"minimum": 0},
        ),
        PolicyCheckResult(
            code="SAFETY_STOCK",
            passed=selected.projected_ending_quantity >= selected.safety_stock_quantity,
            severity="hard",
            detail="Projected ending inventory must meet the safety-stock target.",
            actual=selected.projected_ending_quantity,
            expected={"minimum": selected.safety_stock_quantity},
        ),
        PolicyCheckResult(
            code="AUTO_SPEND_LIMIT",
            passed=spend <= context.auto_spend_limit_minor,
            severity="authorization",
            detail="Spend above the automatic authority limit requires buyer review.",
            actual=spend,
            expected={"maximum": context.auto_spend_limit_minor},
        ),
        PolicyCheckResult(
            code="APPROVED_SUPPLIER",
            passed=supplier.approved,
            severity="authorization",
            detail="An unapproved supplier requires buyer review.",
            actual=str(supplier.approved).lower(),
            expected="true",
        ),
    ]
