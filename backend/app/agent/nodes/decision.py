import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.prompts import DECISION_SYSTEM_PROMPT
from app.agent.provider import ResolvedProvider, create_chat_model
from app.agent.state import PurchasingState, append_step
from app.domain.policy import analyze_purchase
from app.domain.schemas import (
    AuthorizationResult,
    BudgetEvidence,
    CapacityEvidence,
    CaseContext,
    DecisionDraft,
    EvidenceAssessment,
    ForecastEvidence,
    InventoryEvidence,
    OpenOrdersEvidence,
    PurchasingAnalysis,
    SupplierEvidence,
)

logger = logging.getLogger(__name__)


def calculate_requirement(state: PurchasingState) -> PurchasingState:
    evidence = state["evidence"]
    analysis = analyze_purchase(
        context=CaseContext.model_validate(state["context"]),
        inventory=InventoryEvidence.model_validate(evidence["get_inventory"]),
        forecast=ForecastEvidence.model_validate(evidence["get_demand_forecast"]),
        open_orders=OpenOrdersEvidence.model_validate(evidence["get_open_purchase_orders"]),
        supplier=SupplierEvidence.model_validate(evidence["get_supplier_terms"]),
        budget=BudgetEvidence.model_validate(evidence["get_budget"]),
        capacity=CapacityEvidence.model_validate(evidence["get_storage_capacity"]),
    )
    return {
        "analysis": analysis.model_dump(mode="json"),
        "steps": append_step(state, "calculate_requirement"),
    }


def replay_decision(analysis: PurchasingAnalysis) -> DecisionDraft:
    summaries = {
        "accept": "The recommendation matches the smallest safe, pack-valid order.",
        "modify": "The recommendation should be reduced to the smallest safe, pack-valid order.",
        "reject": "Current and incoming inventory already cover demand and safety stock.",
        "investigate": "No safe purchase can proceed until the blocking condition is resolved.",
    }
    return DecisionDraft(
        decision=analysis.expected_decision,
        candidate_id=analysis.expected_candidate_id,
        reason_codes=analysis.reason_codes,
        summary=summaries[analysis.expected_decision],
    )


def propose_decision(
    state: PurchasingState,
    provider: ResolvedProvider | None,
) -> PurchasingState:
    assessment = EvidenceAssessment.model_validate(state["evidence_assessment"])
    if not assessment.complete:
        draft = DecisionDraft(
            decision="investigate",
            candidate_id=None,
            reason_codes=assessment.reason_codes,
            summary="Critical purchasing evidence is missing or stale, so no action is safe.",
        )
    else:
        analysis = PurchasingAnalysis.model_validate(state["analysis"])
        draft = _create_decision(state, analysis, provider)

    return {
        "decision": draft.model_dump(mode="json"),
        "steps": append_step(state, "propose_decision"),
    }


def _create_decision(
    state: PurchasingState,
    analysis: PurchasingAnalysis,
    provider: ResolvedProvider | None,
) -> DecisionDraft:
    if state["mode"] == "replay":
        return replay_decision(analysis)

    try:
        model = create_chat_model(provider)
        structured_model = model.with_structured_output(DecisionDraft)
        result = structured_model.invoke(
            [
                SystemMessage(content=DECISION_SYSTEM_PROMPT),
                HumanMessage(
                    content=json.dumps(
                        {
                            "recommendation_quantity": state["context"][
                                "recommended_quantity"
                            ],
                            "analysis": analysis.model_dump(
                                mode="json",
                                exclude={"candidates": {"__all__": {"projection"}}},
                            ),
                        }
                    )
                ),
            ]
        )
        return DecisionDraft.model_validate(result)
    except Exception:
        logger.exception("The configured model could not propose a purchasing decision")
        return DecisionDraft(
            decision="investigate",
            candidate_id=None,
            reason_codes=["model_unavailable"],
            summary="The configured model was unavailable, so no action was permitted.",
        )


def validate_plan(state: PurchasingState) -> PurchasingState:
    assessment = EvidenceAssessment.model_validate(state["evidence_assessment"])
    draft = DecisionDraft.model_validate(state["decision"])
    if not assessment.complete or "analysis" not in state:
        authorization = AuthorizationResult(
            status="blocked",
            reason_codes=assessment.reason_codes or ["analysis_unavailable"],
            detail="Automatic action is blocked until complete, current evidence is available.",
        )
        return _validation_state(state, authorization, None)

    analysis = PurchasingAnalysis.model_validate(state["analysis"])
    plan_matches_policy = (
        draft.decision == analysis.expected_decision
        and draft.candidate_id == analysis.expected_candidate_id
    )
    if not plan_matches_policy:
        blocked_draft = DecisionDraft(
            decision="investigate",
            candidate_id=None,
            reason_codes=["model_plan_failed_policy_validation"],
            summary="The model proposal did not match a policy-valid purchasing action.",
        )
        authorization = AuthorizationResult(
            status="blocked",
            reason_codes=["model_plan_failed_policy_validation"],
            detail="The model proposal cannot execute because deterministic validation rejected it.",
        )
        result = _validation_state(state, authorization, None)
        result["decision"] = blocked_draft.model_dump(mode="json")
        return result

    selected = next(
        (
            candidate
            for candidate in analysis.candidates
            if candidate.id == analysis.expected_candidate_id
        ),
        None,
    )
    authorization = _authorize_candidate(draft, analysis, selected)
    return _validation_state(state, authorization, selected)


def _authorize_candidate(draft, analysis, selected) -> AuthorizationResult:
    if draft.decision == "reject":
        return AuthorizationResult(
            status="not_required",
            reason_codes=analysis.reason_codes,
            detail="No purchasing action is required.",
        )
    if draft.decision == "investigate" or selected is None:
        return AuthorizationResult(
            status="blocked",
            reason_codes=analysis.reason_codes,
            detail="The proposed purchase is blocked until the constraint is resolved.",
        )

    hard_failures = [
        check.code
        for check in analysis.policy_checks
        if check.severity == "hard" and not check.passed
    ]
    review_reasons = [
        check.code
        for check in analysis.policy_checks
        if check.severity == "authorization" and not check.passed
    ]
    if hard_failures:
        return AuthorizationResult(
            status="blocked",
            reason_codes=hard_failures,
            detail="One or more hard purchasing constraints failed.",
        )
    if review_reasons:
        return AuthorizationResult(
            status="human_review",
            reason_codes=review_reasons,
            detail="The action is feasible but exceeds automatic authority.",
        )
    return AuthorizationResult(
        status="auto_authorized",
        reason_codes=["within_automatic_authority"],
        detail="The action is feasible and within automatic authority.",
    )


def _validation_state(state, authorization, selected) -> PurchasingState:
    return {
        "preliminary_authorization": authorization.model_dump(mode="json"),
        "selected_candidate": selected.model_dump(mode="json") if selected else None,
        "steps": append_step(state, "validate_plan"),
    }
