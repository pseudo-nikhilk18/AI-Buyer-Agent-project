from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from langgraph.types import Command
from sqlalchemy import delete

from app.agent.checkpoint import open_checkpointer
from app.agent.graph import build_purchasing_graph
from app.agent.provider import resolve_provider, resolve_run_provider
from app.agent.state import PurchasingState
from app.config import get_settings
from app.database import session_scope
from app.domain.evidence import parse_observed_at
from app.domain.schemas import CaseContext, ReviewDecision
from app.models import (
    AgentRun,
    EvidenceRecord,
    PolicyCheck,
    PurchasingCase,
    ValidationResult,
)
from app.purchasing_tools import get_case_context


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowStateError(RuntimeError):
    pass


def interrupt_payload(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return None
    return jsonable_encoder(interrupts[0].value)


def clean_state(result: dict) -> PurchasingState:
    return {key: jsonable_encoder(value) for key, value in result.items() if key != "__interrupt__"}


def persist_run_state(
    run_id: UUID,
    state: PurchasingState,
    review_request: dict | None = None,
) -> None:
    with session_scope() as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            raise WorkflowNotFoundError("Agent run was not found.")

        decision = state.get("decision", {})
        authorization = state.get("authorization") or state.get("preliminary_authorization", {})
        selected = state.get("selected_candidate") or {}
        status = "awaiting_review" if review_request else state.get("status", "running")
        snapshot = dict(state)
        if review_request:
            snapshot["review_request"] = review_request

        run.status = status
        run.decision = decision.get("decision")
        run.authorization = authorization.get("status")
        run.proposed_quantity = selected.get("quantity")
        run.proposed_spend_minor = selected.get("spend_minor")
        run.summary = decision.get("summary")
        run.reason_codes = decision.get("reason_codes", [])
        run.error_code = state.get("error_code")
        run.state_snapshot = jsonable_encoder(snapshot)
        if status in {"completed", "blocked", "escalated", "rejected", "failed"}:
            run.completed_at = datetime.now(UTC)

        purchasing_case = session.get(PurchasingCase, run.case_id)
        if purchasing_case is not None:
            purchasing_case.status = status

        session.execute(delete(EvidenceRecord).where(EvidenceRecord.run_id == run_id))
        assessment = state.get("evidence_assessment", {})
        stale_tools = set(assessment.get("stale_tools", []))
        for tool_name, payload in state.get("evidence", {}).items():
            observed_at = parse_observed_at(payload)
            if observed_at is None or "error" in payload:
                continue
            session.add(
                EvidenceRecord(
                    run_id=run_id,
                    tool_name=tool_name,
                    payload=payload,
                    observed_at=observed_at,
                    is_fresh=tool_name not in stale_tools,
                )
            )

        session.execute(delete(PolicyCheck).where(PolicyCheck.run_id == run_id))
        for check in state.get("analysis", {}).get("policy_checks", []):
            session.add(
                PolicyCheck(
                    run_id=run_id,
                    code=check["code"],
                    passed=check["passed"],
                    severity=check["severity"],
                    detail=check["detail"],
                    actual=check.get("actual"),
                    expected=check.get("expected"),
                )
            )

        session.execute(delete(ValidationResult).where(ValidationResult.run_id == run_id))
        validation = state.get("validation")
        if validation:
            session.add(
                ValidationResult(
                    run_id=run_id,
                    status=validation["status"],
                    expected_quantity=validation.get("expected_quantity"),
                    actual_quantity=validation.get("actual_quantity"),
                    detail=validation["detail"],
                )
            )


def start_case_run(case_id: UUID) -> UUID:
    settings = get_settings()
    provider = resolve_provider(settings)
    run_id = uuid4()
    thread_id = str(uuid4())
    with session_scope() as session:
        purchasing_case = session.get(PurchasingCase, case_id)
        if purchasing_case is None:
            raise WorkflowNotFoundError("Purchasing case was not found.")
        context = get_case_context(session, case_id)
        session.add(
            AgentRun(
                id=run_id,
                case_id=case_id,
                thread_id=thread_id,
                mode=settings.ai_mode,
                provider=provider.name if provider else None,
                model=provider.model if provider else None,
                status="running",
            )
        )

    initial_state: PurchasingState = {
        "run_id": str(run_id),
        "case_id": str(case_id),
        "mode": settings.ai_mode,
        "provider": provider.name if provider else None,
        "model": provider.model if provider else None,
        "context": CaseContext.model_validate(context).model_dump(mode="json"),
        "replan_count": 0,
        "steps": [],
    }
    config = {"configurable": {"thread_id": thread_id}}
    with open_checkpointer() as checkpointer:
        graph = build_purchasing_graph(checkpointer, provider)
        result = graph.invoke(initial_state, config=config)
    review_request = interrupt_payload(result)
    persist_run_state(run_id, clean_state(result), review_request)
    return run_id


def resume_case_run(run_id: UUID, review: ReviewDecision) -> UUID:
    settings = get_settings()
    with session_scope() as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            raise WorkflowNotFoundError("Agent run was not found.")
        if run.status != "awaiting_review":
            raise WorkflowStateError("Only a run awaiting review can be resumed.")
        thread_id = run.thread_id
        provider = resolve_run_provider(
            run.mode,
            run.provider,
            run.model,
            settings,
        )

    config = {"configurable": {"thread_id": thread_id}}
    with open_checkpointer() as checkpointer:
        graph = build_purchasing_graph(checkpointer, provider)
        result = graph.invoke(Command(resume=review.model_dump(mode="json")), config=config)
    next_review = interrupt_payload(result)
    persist_run_state(run_id, clean_state(result), next_review)
    return run_id
