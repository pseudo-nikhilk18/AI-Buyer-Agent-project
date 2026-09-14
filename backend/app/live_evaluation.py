import argparse
import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from time import monotonic, sleep
from uuid import UUID

from sqlalchemy import func, select

from app.agent.checkpoint import setup_checkpointer
from app.agent.prompts import DECISION_SYSTEM_PROMPT, INVESTIGATION_SYSTEM_PROMPT
from app.agent.provider import ResolvedProvider, resolve_provider
from app.config import get_settings
from app.database import session_scope
from app.domain.schemas import ReviewDecision
from app.evals.dataset import (
    EvaluationExample,
    dataset_sha256,
    load_evaluation_dataset,
)
from app.evals.graders import (
    find_hard_safety_failures,
    grade_decision,
    grade_final_outcome,
    grade_tool_trajectory,
)
from app.evals.judge import judge_explanation
from app.evals.reporting import percentile, write_live_artifacts
from app.models import AgentRun, PurchaseOrder, PurchasingCase
from app.seed import seed_demo_data
from app.services.workflow import resume_case_run, start_case_run


EVALUATION_TYPE = "live_agent_experiment"


class LiveEvaluationConfigurationError(RuntimeError):
    pass


def _require_live_provider() -> ResolvedProvider:
    settings = get_settings()
    if settings.ai_mode != "live":
        raise LiveEvaluationConfigurationError(
            "Live evaluation requires AI_MODE=live and provider credentials. "
            "Use `python -m app.system_regression` for the no-key safety regression."
        )
    provider = resolve_provider(settings)
    if provider is None:
        raise LiveEvaluationConfigurationError("A live provider and model are required.")
    return provider


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_case_id(case_code: str) -> UUID:
    with session_scope() as session:
        case_id = session.scalar(
            select(PurchasingCase.id).where(PurchasingCase.code == case_code)
        )
    if case_id is None:
        raise RuntimeError(f"Seeded case {case_code} was not found.")
    return case_id


def _run_live_trial(
    *,
    example: EvaluationExample,
    trial_number: int,
    provider: ResolvedProvider,
    use_judge: bool,
) -> dict:
    # Every trial starts from identical inputs so earlier actions cannot alter later scores.
    with session_scope() as session:
        seed_demo_data(session)
    case_id = _load_case_id(example.case_code)
    started = monotonic()

    # Only the case ID enters the product graph. Reference labels are first read by
    # the graders below, after the graph has produced its complete result.
    run_id = start_case_run(case_id)
    with session_scope() as session:
        initial_status = session.scalar(
            select(AgentRun.status).where(AgentRun.id == run_id)
        )

    if initial_status == "awaiting_review":
        resume_case_run(
            run_id,
            ReviewDecision(
                decision="approve",
                note="Approved to complete the evaluation of the post-approval path.",
            ),
        )

    with session_scope() as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            raise RuntimeError(f"Run {run_id} disappeared before grading.")
        state = run.state_snapshot
        orders = session.scalars(
            select(PurchaseOrder).where(
                PurchaseOrder.case_id == case_id,
                PurchaseOrder.idempotency_key.is_not(None),
            )
        ).all()
        order_count = session.scalar(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.case_id == case_id,
                PurchaseOrder.idempotency_key.is_not(None),
            )
        ) or 0

    persisted_quantity = orders[0].quantity if len(orders) == 1 else None
    trajectory_grade = grade_tool_trajectory(state, example.reference)
    decision_grade = grade_decision(state, example.reference)
    final_grade = grade_final_outcome(
        state=state,
        reference=example.reference,
        initial_status=initial_status,
        run_status=run.status,
        order_count=order_count,
        persisted_quantity=persisted_quantity,
    )
    safety_failures = find_hard_safety_failures(
        state=state,
        run_status=run.status,
        order_count=order_count,
    )

    target_error = run.error_code or state.get("error_code")
    judgment = None
    judge_error = None
    if use_judge and target_error is None:
        try:
            judgment = judge_explanation(
                provider=provider,
                example=example,
                state=state,
            )
        except Exception as error:  # preserve the target result if the judge is unavailable
            judge_error = f"{type(error).__name__}: {error}"

    decision = state.get("decision", {})
    raw = state.get("raw_ai_proposal") or {}
    action = state.get("action") or {}
    duration_ms = round((monotonic() - started) * 1000)
    passed = bool(
        trajectory_grade["passed"]
        and decision_grade["passed"]
        and final_grade["passed"]
        and not safety_failures
    )
    return {
        "evaluation_id": example.id,
        "case_code": example.case_code,
        "category": example.metadata.category,
        "difficulty": example.metadata.difficulty,
        "trial": trial_number,
        "run_id": str(run_id),
        "duration_ms": duration_ms,
        "provider": run.provider,
        "model": run.model,
        "scored": target_error is None,
        "target_error": target_error,
        "passed": passed,
        "expected": example.reference.model_dump(),
        "observed": {
            "raw_decision": raw.get("decision"),
            "raw_candidate_id": raw.get("candidate_id"),
            "guarded_decision": decision.get("decision"),
            "guarded_candidate_id": decision.get("candidate_id"),
            "authorization": state.get("authorization", {}).get("status"),
            "final_status": run.status,
            "requested_quantity": action.get("requested_quantity"),
            "persisted_quantity": persisted_quantity,
            "validation": state.get("validation", {}).get("status"),
        },
        "grades": {
            "trajectory": trajectory_grade,
            "decision": decision_grade,
            "final_outcome": final_grade,
        },
        "explanation_judge": judgment,
        "judge_error": judge_error,
        "hard_safety_failures": safety_failures,
        "trace": {
            "steps": state.get("steps", []),
            "investigation_history": state.get("investigation_history", []),
            "decision_guard": state.get("decision_guard"),
        },
    }


def _stability_summary(results: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        grouped[result["case_code"]].append(result)

    summaries = []
    for case_code, trials in grouped.items():
        signatures = {
            (
                item["observed"]["raw_decision"],
                item["observed"]["raw_candidate_id"],
                item["observed"]["guarded_decision"],
                item["observed"]["requested_quantity"],
                item["observed"]["final_status"],
            )
            for item in trials
        }
        summaries.append(
            {
                "case_code": case_code,
                "trials": len(trials),
                "unique_outcomes": len(signatures),
                "measured": len(trials) > 1,
                "consistent": len(signatures) == 1,
                "pass_rate": round(sum(item["passed"] for item in trials) / len(trials), 3),
            }
        )
    return summaries


def run_live_evaluations(
    *,
    suite: str = "quick",
    case_codes: set[str] | None = None,
    repetitions: int = 1,
    use_judge: bool = False,
    delay_seconds: float = 0,
) -> dict:
    if repetitions < 1:
        raise LiveEvaluationConfigurationError("Repetitions must be at least 1.")
    if delay_seconds < 0:
        raise LiveEvaluationConfigurationError("Delay cannot be negative.")

    provider = _require_live_provider()
    dataset = load_evaluation_dataset()
    selected = (
        [item for item in dataset.examples if item.case_code in case_codes]
        if case_codes
        else dataset.select(suite=suite)
    )
    if not selected:
        raise LiveEvaluationConfigurationError("No matching evaluation cases were selected.")
    if case_codes:
        found = {item.case_code for item in selected}
        missing = sorted(case_codes - found)
        if missing:
            raise LiveEvaluationConfigurationError(
                f"Unknown evaluation cases: {', '.join(missing)}"
            )

    setup_checkpointer()
    experiment_started = monotonic()
    results: list[dict] = []
    total_trials = len(selected) * repetitions
    completed = 0
    for example in selected:
        for trial_number in range(1, repetitions + 1):
            results.append(
                _run_live_trial(
                    example=example,
                    trial_number=trial_number,
                    provider=provider,
                    use_judge=use_judge,
                )
            )
            completed += 1
            if delay_seconds and completed < total_trials:
                sleep(delay_seconds)

    scored_results = [item for item in results if item["scored"]]
    stability = _stability_summary(scored_results)
    raw_expected = [
        item
        for item in scored_results
        if item["grades"]["decision"]["raw_expected"]
    ]
    judged = [item["explanation_judge"] for item in results if item["explanation_judge"]]
    summary = {
        "total_cases": len(selected),
        "total_trials": len(results),
        "scored_trials": len(scored_results),
        "target_errors": len(results) - len(scored_results),
        "passed_trials": sum(item["passed"] for item in scored_results),
        "trajectory_success_rate": round(
            sum(item["grades"]["trajectory"]["passed"] for item in scored_results)
            / len(scored_results),
            4,
        )
        if scored_results
        else None,
        "mean_tool_recall": round(
            sum(item["grades"]["trajectory"]["recall"] for item in scored_results)
            / len(scored_results),
            4,
        )
        if scored_results
        else None,
        "raw_decision_accuracy": (
            round(
                sum(item["grades"]["decision"]["raw_correct"] for item in raw_expected)
                / len(raw_expected),
                4,
            )
            if raw_expected
            else 1.0
        )
        if scored_results
        else None,
        "grounded_explanation_rate": round(
            sum(
                item["grades"]["decision"]["explanation_grounded"]
                for item in scored_results
            )
            / len(scored_results),
            4,
        )
        if scored_results
        else None,
        "final_outcome_accuracy": round(
            sum(item["grades"]["final_outcome"]["passed"] for item in scored_results)
            / len(scored_results),
            4,
        )
        if scored_results
        else None,
        "unsafe_action_rate": round(
            sum(bool(item["hard_safety_failures"]) for item in results) / len(results),
            4,
        ),
        "hard_safety_failures": sum(
            len(item["hard_safety_failures"]) for item in results
        ),
        "stability_evaluated_cases": sum(item["measured"] for item in stability),
        "stable_cases": sum(
            item["measured"] and item["consistent"] for item in stability
        ),
        "latency_p50_ms": percentile(
            [item["duration_ms"] for item in scored_results], 0.5
        )
        if scored_results
        else None,
        "latency_p95_ms": percentile(
            [item["duration_ms"] for item in scored_results], 0.95
        )
        if scored_results
        else None,
        "judge_mean_score": round(
            sum(item["mean_score"] for item in judged) / len(judged), 2
        )
        if judged
        else None,
        "judge_failures": sum(item["passed"] is False for item in judged),
        "judge_errors": sum(item["judge_error"] is not None for item in results),
    }
    report = {
        "evaluation_type": EVALUATION_TYPE,
        "generated_at": datetime.now(UTC).isoformat(),
        "duration_ms": round((monotonic() - experiment_started) * 1000),
        "provider": provider.name,
        "model": provider.model,
        "suite": suite if case_codes is None else "selected",
        "repetitions": repetitions,
        "dataset": {
            "id": dataset.dataset_id,
            "version": dataset.version,
            "sha256": dataset_sha256(),
            "selected_examples": [item.id for item in selected],
        },
        "prompts": {
            "investigation_sha256": _fingerprint(INVESTIGATION_SYSTEM_PROMPT),
            "decision_sha256": _fingerprint(DECISION_SYSTEM_PROMPT),
        },
        "judge": {
            "enabled": use_judge,
            "provider": provider.name if use_judge else None,
            "model": provider.model if use_judge else None,
            "same_model_as_target": use_judge,
            "gates_core_pass": False,
        },
        "summary": summary,
        "stability": stability,
        "trials": results,
    }
    write_live_artifacts(report)
    return report


def main() -> None:
    dataset = load_evaluation_dataset()
    parser = argparse.ArgumentParser(
        description=(
            "Run a dataset-backed live-agent experiment. Gold references remain outside "
            "the purchasing graph and are applied only after each run."
        )
    )
    parser.add_argument(
        "--suite",
        choices=["quick", "full"],
        default="quick",
        help="Quick runs six core cases; full runs all robustness cases.",
    )
    parser.add_argument(
        "--case",
        action="append",
        choices=[item.case_code for item in dataset.examples],
        dest="case_codes",
        help="Run a named case. Repeat for multiple cases; overrides --suite.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Repeat each case from a clean database state to measure stability.",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Add an optional model rubric for explanation quality; it never masks core scores.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0,
        help="Pause between trials when using a rate-limited free API key.",
    )
    arguments = parser.parse_args()
    try:
        report = run_live_evaluations(
            suite=arguments.suite,
            case_codes=set(arguments.case_codes) if arguments.case_codes else None,
            repetitions=arguments.repetitions,
            use_judge=arguments.judge,
            delay_seconds=arguments.delay_seconds,
        )
    except LiveEvaluationConfigurationError as error:
        raise SystemExit(str(error)) from error

    summary = report["summary"]
    raw_accuracy = summary["raw_decision_accuracy"]
    raw_accuracy_text = "not scored" if raw_accuracy is None else f"{raw_accuracy:.1%}"
    print(
        f"Live experiment: {summary['passed_trials']}/{summary['scored_trials']} scored trials "
        f"passed; target errors: {summary['target_errors']}; "
        f"raw decision accuracy: {raw_accuracy_text}; "
        f"unsafe-action rate: {summary['unsafe_action_rate']:.1%}; "
        f"judge errors: {summary['judge_errors']}."
    )
    if (
        summary["target_errors"]
        or summary["passed_trials"] != summary["scored_trials"]
        or (
        arguments.judge and summary["judge_errors"]
        )
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
