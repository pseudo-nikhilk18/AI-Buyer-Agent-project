from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.provider import ProviderConfigurationError
from app.database import get_db
from app.domain.evidence import assess_evidence
from app.domain.schemas import (
    ActionResult,
    AuthorizationResult,
    BudgetEvidence,
    CapacityEvidence,
    DecisionDraft,
    DecisionGuardResult,
    EvidenceAssessment,
    ForecastEvidence,
    InventoryEvidence,
    InvestigationAttempt,
    InvestigationPlan,
    OpenOrdersEvidence,
    OutcomeValidation,
    PurchaseCandidate,
    PurchasingAnalysis,
    ReviewDecision,
    SupplierEvidence,
)
from app.evals.dataset import public_example_metadata
from app.models import AgentRun, EvidenceRecord, PurchasingCase
from app.purchasing_tools import (
    get_budget,
    get_case_context,
    get_demand_forecast,
    get_inventory,
    get_open_purchase_orders,
    get_storage_capacity,
    get_supplier_terms,
)
from app.services.workflow import (
    WorkflowNotFoundError,
    WorkflowStateError,
    resume_case_run,
    start_case_run,
)

router = APIRouter(prefix="/cases", tags=["purchasing cases"])
runs_router = APIRouter(prefix="/runs", tags=["agent runs"])


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseSummary(ApiModel):
    id: UUID
    code: str
    title: str
    scenario_type: str
    product_name: str
    node_name: str
    recommended_quantity: int
    status: str
    latest_decision: str | None
    latest_run_status: str | None
    test_purpose: str
    test_dimensions: list[str]


class ReviewRequest(ApiModel):
    case_id: UUID
    decision: DecisionDraft
    proposed_quantity: int
    proposed_spend_minor: int
    currency: str
    reason_codes: list[str]


class EvidenceView(ApiModel):
    tool_name: str
    observed_at: datetime
    is_fresh: bool
    payload: dict | list


class RunView(ApiModel):
    id: UUID
    case_id: UUID
    mode: str
    provider: str | None
    model: str | None
    status: str
    error_code: str | None
    decision: DecisionDraft | None
    raw_ai_proposal: DecisionDraft | None
    decision_guard: DecisionGuardResult | None
    authorization: AuthorizationResult | None
    proposed_quantity: int | None
    proposed_spend_minor: int | None
    investigation_plan: InvestigationPlan | None
    investigation_history: list[InvestigationAttempt]
    evidence_assessment: EvidenceAssessment | None
    evidence: list[EvidenceView]
    analysis: PurchasingAnalysis | None
    selected_candidate: PurchaseCandidate | None
    action: ActionResult | None
    validation: OutcomeValidation | None
    review_request: ReviewRequest | None
    steps: list[str]
    started_at: datetime
    completed_at: datetime | None


class CaseDetail(ApiModel):
    id: UUID
    code: str
    title: str
    scenario_type: str
    product_name: str
    sku: str
    node_name: str
    recommended_quantity: int
    status: str
    inventory: InventoryEvidence
    forecast: ForecastEvidence
    open_purchase_orders: OpenOrdersEvidence
    supplier: SupplierEvidence
    budget: BudgetEvidence
    storage_capacity: CapacityEvidence
    evidence_assessment: EvidenceAssessment
    latest_run: RunView | None
    test_purpose: str
    test_dimensions: list[str]


def optional_model(model_type, payload):
    return model_type.model_validate(payload) if payload else None


def build_run_view(session: Session, run: AgentRun) -> RunView:
    state = run.state_snapshot or {}
    evidence_rows = session.scalars(
        select(EvidenceRecord)
        .where(EvidenceRecord.run_id == run.id)
        .order_by(EvidenceRecord.tool_name)
    ).all()
    review_payload = state.get("review_request")
    return RunView(
        id=run.id,
        case_id=run.case_id,
        mode=run.mode,
        provider=run.provider,
        model=run.model,
        status=run.status,
        error_code=run.error_code,
        decision=optional_model(DecisionDraft, state.get("decision")),
        raw_ai_proposal=optional_model(DecisionDraft, state.get("raw_ai_proposal")),
        decision_guard=optional_model(DecisionGuardResult, state.get("decision_guard")),
        authorization=optional_model(
            AuthorizationResult,
            state.get("authorization") or state.get("preliminary_authorization"),
        ),
        proposed_quantity=run.proposed_quantity,
        proposed_spend_minor=run.proposed_spend_minor,
        investigation_plan=optional_model(
            InvestigationPlan, state.get("investigation_plan")
        ),
        investigation_history=[
            InvestigationAttempt.model_validate(item)
            for item in state.get("investigation_history", [])
        ],
        evidence_assessment=optional_model(
            EvidenceAssessment, state.get("evidence_assessment")
        ),
        evidence=[
            EvidenceView(
                tool_name=row.tool_name,
                observed_at=row.observed_at,
                is_fresh=row.is_fresh,
                payload=row.payload,
            )
            for row in evidence_rows
        ],
        analysis=optional_model(PurchasingAnalysis, state.get("analysis")),
        selected_candidate=state.get("selected_candidate"),
        action=optional_model(ActionResult, state.get("action")),
        validation=optional_model(OutcomeValidation, state.get("validation")),
        review_request=ReviewRequest.model_validate(review_payload) if review_payload else None,
        steps=state.get("steps", []),
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def get_latest_run(session: Session, case_id: UUID) -> AgentRun | None:
    return session.scalar(
        select(AgentRun)
        .where(AgentRun.case_id == case_id)
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )


@router.get("", response_model=list[CaseSummary])
def list_cases(session: Session = Depends(get_db)) -> list[CaseSummary]:
    public_metadata = public_example_metadata()
    cases = session.scalars(
        select(PurchasingCase)
        .where(PurchasingCase.code.in_(public_metadata))
        .order_by(PurchasingCase.created_at)
    ).all()
    latest_runs: dict[UUID, AgentRun] = {}
    if cases:
        runs = session.scalars(
            select(AgentRun)
            .where(AgentRun.case_id.in_([item.id for item in cases]))
            .order_by(AgentRun.started_at.desc())
        ).all()
        for run in runs:
            latest_runs.setdefault(run.case_id, run)

    response: list[CaseSummary] = []
    for item in cases:
        latest = latest_runs.get(item.id)
        metadata = public_metadata[item.code]
        response.append(
            CaseSummary(
                id=item.id,
                code=item.code,
                title=item.title,
                scenario_type=item.scenario_type,
                product_name=item.product.name,
                node_name=item.node.name,
                recommended_quantity=item.recommended_quantity,
                status=item.status,
                latest_decision=latest.decision if latest else None,
                latest_run_status=latest.status if latest else None,
                test_purpose=metadata.test_purpose,
                test_dimensions=metadata.dimensions,
            )
        )
    return response


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: UUID, session: Session = Depends(get_db)) -> CaseDetail:
    purchasing_case = session.get(PurchasingCase, case_id)
    public_metadata = public_example_metadata()
    if purchasing_case is None or purchasing_case.code not in public_metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    metadata = public_metadata[purchasing_case.code]
    context = get_case_context(session, case_id)
    inventory = get_inventory(session, case_id)
    forecast = get_demand_forecast(session, case_id)
    open_orders = get_open_purchase_orders(session, case_id)
    supplier = get_supplier_terms(session, case_id)
    budget = get_budget(session, case_id)
    capacity = get_storage_capacity(session, case_id)
    evidence = {
        "get_inventory": inventory.model_dump(mode="json"),
        "get_demand_forecast": forecast.model_dump(mode="json"),
        "get_open_purchase_orders": open_orders.model_dump(mode="json"),
        "get_supplier_terms": supplier.model_dump(mode="json"),
        "get_budget": budget.model_dump(mode="json"),
        "get_storage_capacity": capacity.model_dump(mode="json"),
    }
    latest = get_latest_run(session, case_id)
    return CaseDetail(
        id=purchasing_case.id,
        code=purchasing_case.code,
        title=purchasing_case.title,
        scenario_type=purchasing_case.scenario_type,
        product_name=purchasing_case.product.name,
        sku=purchasing_case.product.sku,
        node_name=purchasing_case.node.name,
        recommended_quantity=purchasing_case.recommended_quantity,
        status=purchasing_case.status,
        inventory=inventory,
        forecast=forecast,
        open_purchase_orders=open_orders,
        supplier=supplier,
        budget=budget,
        storage_capacity=capacity,
        evidence_assessment=assess_evidence(context=context, evidence=evidence),
        latest_run=build_run_view(session, latest) if latest else None,
        test_purpose=metadata.test_purpose,
        test_dimensions=metadata.dimensions,
    )


@router.post("/{case_id}/runs", response_model=RunView)
def create_run(case_id: UUID, session: Session = Depends(get_db)) -> RunView:
    try:
        run_id = start_case_run(case_id)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ProviderConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    session.expire_all()
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Run missing.")
    return build_run_view(session, run)


@runs_router.get("/{run_id}", response_model=RunView)
def get_run(run_id: UUID, session: Session = Depends(get_db)) -> RunView:
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return build_run_view(session, run)


@runs_router.post("/{run_id}/review", response_model=RunView)
def review_run(
    run_id: UUID,
    review: ReviewDecision,
    session: Session = Depends(get_db),
) -> RunView:
    try:
        resume_case_run(run_id, review)
    except WorkflowNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except WorkflowStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ProviderConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    session.expire_all()
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Run missing.")
    return build_run_view(session, run)
