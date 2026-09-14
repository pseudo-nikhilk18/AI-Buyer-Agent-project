import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "purchasing_agent_dataset.json"
)

EvidenceToolName = Literal[
    "get_inventory",
    "get_demand_forecast",
    "get_open_purchase_orders",
    "get_supplier_terms",
    "get_budget",
    "get_storage_capacity",
]


class DatasetModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductInput(DatasetModel):
    sku: str
    name: str


class NodeInput(DatasetModel):
    code: str
    name: str


class SupplierInput(DatasetModel):
    code: str
    name: str
    active: bool = True
    approved: bool = True
    reliability_percent: int = Field(ge=0, le=100)


class SupplierTermsInput(DatasetModel):
    unit_cost_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    minimum_order_quantity: int = Field(gt=0)
    case_pack_quantity: int = Field(gt=0)
    lead_time_days: int = Field(ge=0)


class PolicyInput(DatasetModel):
    code: str
    review_period_days: int = Field(gt=0)
    safety_stock_days: int = Field(ge=0)
    inventory_freshness_minutes: int = Field(gt=0)
    forecast_freshness_hours: int = Field(gt=0)
    supplier_freshness_minutes: int = Field(gt=0)
    constraint_freshness_minutes: int = Field(gt=0)
    auto_spend_limit_minor: int = Field(ge=0)


class InventoryInput(DatasetModel):
    on_hand_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    damaged_quantity: int = Field(ge=0)


class ForecastInput(DatasetModel):
    daily_quantity: int = Field(ge=0)
    days: int = Field(ge=1, le=30)
    age_hours: int = Field(ge=0)


class InboundOrderInput(DatasetModel):
    quantity: int = Field(gt=0)
    arrival_days: int = Field(ge=0)
    status: Literal["open", "confirmed"]


class CaseInput(DatasetModel):
    title: str
    scenario_type: str
    recommended_quantity: int = Field(gt=0)
    product: ProductInput
    node: NodeInput
    supplier: SupplierInput
    supplier_terms: SupplierTermsInput
    policy: PolicyInput
    inventory: InventoryInput
    forecast: ForecastInput
    inbound_order: InboundOrderInput | None
    supplier_available_quantity: int = Field(ge=0)
    budget_minor: int = Field(ge=0)
    storage_capacity_quantity: int = Field(ge=0)
    simulator_mode: Literal["normal", "persist_short"] = "normal"
    omitted_evidence: list[EvidenceToolName] = Field(default_factory=list)


class ReferenceOutcome(DatasetModel):
    decision: Literal["accept", "modify", "reject", "investigate"]
    candidate_id: Literal[
        "no_action", "original_recommendation", "calculated_order"
    ] | None
    authorization: Literal[
        "auto_authorized", "human_approved", "blocked", "not_required"
    ]
    final_status: Literal["completed", "blocked", "escalated"]
    quantity: int | None
    validation: Literal["validated", "failed", "not_required"]
    raw_ai_proposal_expected: bool = True
    requires_review: bool = False
    required_reason_codes: list[str] = Field(default_factory=list)
    required_tools: list[EvidenceToolName]


class ExampleMetadata(DatasetModel):
    suite: Literal["quick", "full"]
    ui_visible: bool
    category: str
    difficulty: Literal["standard", "edge", "adversarial"]
    test_purpose: str
    dimensions: list[str]
    tags: list[str]


class EvaluationExample(DatasetModel):
    id: str
    case_code: str
    input: CaseInput
    reference: ReferenceOutcome
    metadata: ExampleMetadata


class EvaluationDataset(DatasetModel):
    dataset_id: str
    version: str
    description: str
    examples: list[EvaluationExample]

    @model_validator(mode="after")
    def require_unique_identifiers(self):
        if len({item.id for item in self.examples}) != len(self.examples):
            raise ValueError("Evaluation example IDs must be unique.")
        if len({item.case_code for item in self.examples}) != len(self.examples):
            raise ValueError("Evaluation case codes must be unique.")
        return self

    def select(
        self,
        *,
        suite: Literal["quick", "full"] = "full",
        case_codes: set[str] | None = None,
    ) -> list[EvaluationExample]:
        examples = [
            item
            for item in self.examples
            if suite == "full" or item.metadata.suite == "quick"
        ]
        if case_codes is not None:
            examples = [item for item in examples if item.case_code in case_codes]
        return examples


@lru_cache(maxsize=1)
def load_evaluation_dataset() -> EvaluationDataset:
    return EvaluationDataset.model_validate_json(DATASET_PATH.read_text(encoding="utf-8"))


def dataset_sha256() -> str:
    parsed = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def public_example_metadata() -> dict[str, ExampleMetadata]:
    return {
        item.case_code: item.metadata
        for item in load_evaluation_dataset().examples
        if item.metadata.ui_visible
    }
