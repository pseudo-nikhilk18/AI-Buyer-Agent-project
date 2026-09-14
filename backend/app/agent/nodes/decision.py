import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.prompts import DECISION_SYSTEM_PROMPT
from app.agent.provider import ResolvedProvider, create_chat_model
from app.agent.state import PurchasingState, append_step
from app.domain.policy import analyze_purchase, build_policy_checks
from app.domain.schemas import (
    AuthorizationResult,
    BudgetEvidence,
    CapacityEvidence,
    CaseContext,
    DecisionDraft,
    DecisionGuardResult,
    EvidenceAssessment,
    ForecastEvidence,
    InventoryEvidence,
    OpenOrdersEvidence,
    PurchasingAnalysis,
    SupplierEvidence,
)

logger = logging.getLogger(__name__)


DECISION_REASON_CODES = {
    "recommendation_matches_safe_quantity",
    "recommendation_differs_from_safe_quantity",
    "inventory_coverage_sufficient",
    "calculated_order_blocked",
    "no_feasible_candidate",
}


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
        decision=analysis.policy_decision,
        candidate_id=analysis.policy_candidate_id,
        reason_codes=analysis.reason_codes,
        summary=summaries[analysis.policy_decision],
    )


def _neutral_operational_context(state: PurchasingState) -> dict:
    context = state["context"]
    allowed_fields = (
        "product_id",
        "product_name",
        "sku",
        "node_id",
        "node_name",
        "supplier_id",
        "recommended_quantity",
    )
    return {field: context[field] for field in allowed_fields}


def _available_reason_codes(analysis: PurchasingAnalysis) -> list[str]:
    codes = set(DECISION_REASON_CODES)
    for candidate in analysis.candidates:
        codes.update(candidate.violations)
    for check in analysis.policy_checks:
        codes.add(check.code)
        codes.add(check.code.lower())
    return sorted(codes)


def build_decision_prompt_payload(
    state: PurchasingState,
    analysis: PurchasingAnalysis,
) -> dict:
    evidence = state["evidence"]
    context = CaseContext.model_validate(state["context"])
    supplier = SupplierEvidence.model_validate(evidence["get_supplier_terms"])
    budget = BudgetEvidence.model_validate(evidence["get_budget"])
    capacity = CapacityEvidence.model_validate(evidence["get_storage_capacity"])
    candidate_policy_checks = [
        {
            "candidate_id": candidate.id,
            "checks": [
                check.model_dump(mode="json")
                for check in build_policy_checks(
                    context=context,
                    supplier=supplier,
                    budget=budget,
                    capacity=capacity,
                    selected=candidate,
                )
            ],
        }
        for candidate in analysis.candidates
    ]
    return {
        "operational_context": _neutral_operational_context(state),
        "evidence": evidence,
        "candidates": [candidate.model_dump(mode="json") for candidate in analysis.candidates],
        "policy_checks": candidate_policy_checks,
        "available_reason_codes": _available_reason_codes(analysis),
    }


def propose_decision(
    state: PurchasingState,
    provider: ResolvedProvider | None,
) -> PurchasingState:
    assessment = EvidenceAssessment.model_validate(state["evidence_assessment"])
    raw_ai_proposal = None
    if not assessment.complete:
        draft = DecisionDraft(
            decision="investigate",
            candidate_id=None,
            reason_codes=assessment.reason_codes,
            summary="Critical purchasing evidence is missing or stale, so no action is safe.",
        )
    else:
        analysis = PurchasingAnalysis.model_validate(state["analysis"])
        draft, raw_ai_proposal = _create_decision(state, analysis, provider)

    result: PurchasingState = {
        "raw_ai_proposal": (
            raw_ai_proposal.model_dump(mode="json") if raw_ai_proposal else None
        ),
        "decision": draft.model_dump(mode="json"),
        "steps": append_step(state, "propose_decision"),
    }
    if draft.reason_codes == ["model_unavailable"]:
        result["error_code"] = "MODEL_UNAVAILABLE"
    return result


def _create_decision(
    state: PurchasingState,
    analysis: PurchasingAnalysis,
    provider: ResolvedProvider | None,
) -> tuple[DecisionDraft, DecisionDraft | None]:
    if state["mode"] == "replay":
        return replay_decision(analysis), None

    try:
        model = create_chat_model(provider)
        structured_model = model.with_structured_output(DecisionDraft)
        result = structured_model.invoke(
            [
                SystemMessage(content=DECISION_SYSTEM_PROMPT),
                HumanMessage(
                    content=json.dumps(build_decision_prompt_payload(state, analysis))
                ),
            ]
        )
        raw_proposal = DecisionDraft.model_validate(result)
        return raw_proposal, raw_proposal
    except Exception:
        logger.exception("The configured model could not propose a purchasing decision")
        return (
            DecisionDraft(
                decision="investigate",
                candidate_id=None,
                reason_codes=["model_unavailable"],
                summary="The configured model was unavailable, so no action was permitted.",
            ),
            None,
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
        guard = DecisionGuardResult(
            status="blocked",
            reason_codes=assessment.reason_codes or ["analysis_unavailable"],
            detail=(
                "The safety guard stopped the proposal because required evidence was "
                "unavailable."
            ),
        )
        return _validation_state(state, authorization, None, guard)

    if state.get("error_code") == "MODEL_UNAVAILABLE":
        authorization = AuthorizationResult(
            status="blocked",
            reason_codes=["model_unavailable"],
            detail="Automatic action is blocked because the configured model was unavailable.",
        )
        guard = DecisionGuardResult(
            status="blocked",
            reason_codes=["model_unavailable"],
            detail="The safety guard stopped the run because no live model proposal was produced.",
        )
        return _validation_state(state, authorization, None, guard)

    analysis = PurchasingAnalysis.model_validate(state["analysis"])
    allowed_reason_codes = set(_available_reason_codes(analysis))
    reasons_are_grounded = all(code in allowed_reason_codes for code in draft.reason_codes)
    plan_matches_policy = (
        draft.decision == analysis.policy_decision
        and draft.candidate_id == analysis.policy_candidate_id
        and (state.get("raw_ai_proposal") is None or reasons_are_grounded)
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
            detail=(
                "The model proposal cannot execute because deterministic validation "
                "rejected it."
            ),
        )
        guard = DecisionGuardResult(
            status="blocked",
            reason_codes=["model_plan_failed_policy_validation"],
            detail="The raw model proposal did not match the private loss-bounded policy optimum.",
        )
        result = _validation_state(state, authorization, None, guard)
        result["decision"] = blocked_draft.model_dump(mode="json")
        return result

    selected = next(
        (
            candidate
            for candidate in analysis.candidates
            if candidate.id == analysis.policy_candidate_id
        ),
        None,
    )
    authorization = _authorize_candidate(draft, analysis, selected)
    guard = DecisionGuardResult(
        status="passed",
        reason_codes=["proposal_matches_loss_bounded_policy"],
        detail="The proposal matches the private loss-bounded optimum and uses grounded reasons.",
    )
    return _validation_state(state, authorization, selected, guard)


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


def _validation_state(state, authorization, selected, guard) -> PurchasingState:
    return {
        "decision_guard": guard.model_dump(mode="json"),
        "preliminary_authorization": authorization.model_dump(mode="json"),
        "selected_candidate": selected.model_dump(mode="json") if selected else None,
        "steps": append_step(state, "validate_plan"),
    }
