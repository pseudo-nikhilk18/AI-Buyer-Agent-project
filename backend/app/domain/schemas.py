from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InventoryEvidence(StrictModel):
    on_hand_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    damaged_quantity: int = Field(ge=0)
    observed_at: datetime


class ForecastPoint(StrictModel):
    demand_date: date
    quantity: int = Field(ge=0)


class ForecastEvidence(StrictModel):
    points: list[ForecastPoint]
    observed_at: datetime


class OpenPurchaseOrderEvidence(StrictModel):
    id: str
    quantity: int = Field(gt=0)
    expected_delivery_date: date
    status: str


class OpenOrdersEvidence(StrictModel):
    orders: list[OpenPurchaseOrderEvidence]
    observed_at: datetime


class SupplierEvidence(StrictModel):
    supplier_id: str
    supplier_name: str
    active: bool
    approved: bool
    reliability_percent: int = Field(ge=0, le=100)
    unit_cost_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    minimum_order_quantity: int = Field(gt=0)
    case_pack_quantity: int = Field(gt=0)
    lead_time_days: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    observed_at: datetime


class BudgetEvidence(StrictModel):
    available_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    observed_at: datetime


class CapacityEvidence(StrictModel):
    available_quantity: int = Field(ge=0)
    observed_at: datetime


class CaseContext(StrictModel):
    case_id: str
    code: str
    title: str
    scenario_type: str
    product_id: str
    product_name: str
    sku: str
    node_id: str
    node_name: str
    supplier_id: str
    supplier_name: str
    recommended_quantity: int = Field(gt=0)
    simulator_mode: str
    review_period_days: int = Field(gt=0)
    safety_stock_days: int = Field(ge=0)
    inventory_freshness_minutes: int = Field(gt=0)
    forecast_freshness_hours: int = Field(gt=0)
    supplier_freshness_minutes: int = Field(gt=0)
    constraint_freshness_minutes: int = Field(gt=0)
    auto_spend_limit_minor: int = Field(ge=0)


class EvidenceAssessment(StrictModel):
    complete: bool
    missing_tools: list[str]
    stale_tools: list[str]
    reason_codes: list[str]


class ProjectionPoint(StrictModel):
    date: date
    opening_quantity: int
    incoming_quantity: int = Field(ge=0)
    demand_quantity: int = Field(ge=0)
    closing_quantity: int


class PurchaseCandidate(StrictModel):
    id: Literal["no_action", "original_recommendation", "calculated_order"]
    quantity: int = Field(ge=0)
    arrival_date: date | None
    spend_minor: int = Field(ge=0)
    currency: str
    projected_ending_quantity: int
    projected_minimum_quantity: int
    safety_stock_quantity: int = Field(ge=0)
    surplus_above_safety: int = Field(ge=0)
    shortfall_below_safety: int = Field(ge=0)
    feasible: bool
    violations: list[str]
    projection: list[ProjectionPoint]


class PolicyCheckResult(StrictModel):
    code: str
    passed: bool
    severity: Literal["hard", "authorization", "information"]
    detail: str
    actual: dict | int | str | None = None
    expected: dict | int | str | None = None


class PurchasingAnalysis(StrictModel):
    planning_horizon_days: int = Field(gt=0)
    usable_inventory_quantity: int
    forecast_quantity: int = Field(ge=0)
    safety_stock_quantity: int = Field(ge=0)
    net_requirement_quantity: int = Field(ge=0)
    calculated_order_quantity: int = Field(ge=0)
    policy_decision: Literal["accept", "modify", "reject", "investigate"] = Field(
        validation_alias=AliasChoices("policy_decision", "expected_decision")
    )
    policy_candidate_id: str | None = Field(
        validation_alias=AliasChoices("policy_candidate_id", "expected_candidate_id")
    )
    candidates: list[PurchaseCandidate]
    policy_checks: list[PolicyCheckResult]
    reason_codes: list[str]


EvidenceToolName = Literal[
    "get_inventory",
    "get_demand_forecast",
    "get_open_purchase_orders",
    "get_supplier_terms",
    "get_budget",
    "get_storage_capacity",
]


class InvestigationToolRequest(StrictModel):
    tool_name: EvidenceToolName
    purpose: str = Field(min_length=1, max_length=240)
    questions: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        min_length=1,
        max_length=4,
    )


class InvestigationPlan(StrictModel):
    tool_requests: list[InvestigationToolRequest] = Field(max_length=6)
    summary: str = Field(min_length=1, max_length=400)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_tool_names(cls, value):
        if not isinstance(value, dict) or "tool_requests" in value:
            return value
        legacy_names = value.get("tool_names")
        if not isinstance(legacy_names, list):
            return value
        migrated = {key: item for key, item in value.items() if key != "tool_names"}
        migrated["tool_requests"] = [
            {
                "tool_name": tool_name,
                "purpose": "Retrieve evidence selected by the earlier investigation plan.",
                "questions": ["What current evidence does this source provide?"],
            }
            for tool_name in legacy_names
        ]
        return migrated

    @model_validator(mode="after")
    def reject_duplicate_tools(self):
        if len(self.tool_names) != len(set(self.tool_names)):
            raise ValueError("An investigation plan cannot repeat a tool.")
        return self

    @property
    def tool_names(self) -> list[EvidenceToolName]:
        return [request.tool_name for request in self.tool_requests]


class InvestigationAttempt(StrictModel):
    attempt: int = Field(ge=1, le=2)
    missing_sources_before: list[EvidenceToolName]
    plan: InvestigationPlan


class DecisionDraft(StrictModel):
    decision: Literal["accept", "modify", "reject", "investigate"]
    candidate_id: str | None
    reason_codes: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        min_length=1,
        max_length=12,
    )
    summary: str = Field(min_length=1, max_length=800)


class DecisionGuardResult(StrictModel):
    status: Literal["passed", "blocked"]
    reason_codes: list[str]
    detail: str = Field(min_length=1, max_length=800)


class AuthorizationResult(StrictModel):
    status: Literal[
        "auto_authorized",
        "human_review",
        "human_approved",
        "rejected",
        "blocked",
        "not_required",
    ]
    reason_codes: list[str]
    detail: str


class ReviewDecision(StrictModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=400)


class ActionResult(StrictModel):
    status: Literal[
        "acknowledged",
        "idempotent_replay",
        "replan_required",
        "not_executed",
    ]
    action_type: Literal["create", "none"]
    idempotency_key: str | None
    purchase_order_id: str | None
    requested_quantity: int | None
    reported_quantity: int | None
    reason_code: str | None = None


class OutcomeValidation(StrictModel):
    status: Literal["validated", "failed", "not_required"]
    expected_quantity: int | None
    actual_quantity: int | None
    detail: str
