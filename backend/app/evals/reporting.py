import json
from datetime import datetime
from pathlib import Path


def percentile(values: list[int], percent: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percent)
    return ordered[index]


def format_percent(value: float | None) -> str:
    return "not scored" if value is None else f"{value:.1%}"


def format_latency(value: int | None) -> str:
    return "not scored" if value is None else f"{value} ms"


def write_live_artifacts(report: dict) -> tuple[Path, Path]:
    output_dir = Path(__file__).resolve().parents[3] / "artifacts" / "evaluations" / "live"
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.fromisoformat(report["generated_at"])
    stem = generated.strftime("%Y%m%dT%H%M%SZ")
    timestamped_json = output_dir / f"experiment-{stem}.json"
    latest_json = output_dir / "latest.json"
    latest_markdown = output_dir / "latest.md"
    payload = json.dumps(report, indent=2) + "\n"
    timestamped_json.write_text(payload, encoding="utf-8")
    latest_json.write_text(payload, encoding="utf-8")

    summary = report["summary"]
    lines = [
        "# Latest Live-Agent Evaluation",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Dataset: `{report['dataset']['id']}` v{report['dataset']['version']} (`{report['dataset']['sha256'][:12]}`)",
        f"- Target: `{report['provider']}` / `{report['model']}`",
        f"- Suite / repetitions: `{report['suite']}` / {report['repetitions']}",
        f"- Scored trials: **{summary['passed_trials']}/{summary['scored_trials']} passed**",
        f"- Target errors: **{summary['target_errors']}/{summary['total_trials']} attempts**",
        f"- Raw decision accuracy: **{format_percent(summary['raw_decision_accuracy'])}**",
        f"- Tool-trajectory success: **{format_percent(summary['trajectory_success_rate'])}**",
        f"- Final-outcome accuracy: **{format_percent(summary['final_outcome_accuracy'])}**",
        f"- Unsafe-action rate: **{summary['unsafe_action_rate']:.1%}**",
        f"- Stable repeated cases: **{summary['stable_cases']}/{summary['stability_evaluated_cases']}**",
        f"- Latency p50 / p95: **{format_latency(summary['latency_p50_ms'])} / {format_latency(summary['latency_p95_ms'])}**",
        "",
        "| Test | Trial | Target | Trajectory | Raw decision | Explanation | Final result | Safety |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for result in report["trials"]:
        decision = result["grades"]["decision"]
        if result["target_error"]:
            target = f"error (`{result['target_error']}`)"
            trajectory = raw = explanation = final = "not scored"
        else:
            target = "completed"
            trajectory = "pass" if result["grades"]["trajectory"]["passed"] else "fail"
            raw = (
                "n/a"
                if not decision["raw_expected"]
                else ("pass" if decision["raw_correct"] else "fail")
            )
            explanation = "pass" if decision["explanation_grounded"] else "fail"
            final = "pass" if result["grades"]["final_outcome"]["passed"] else "fail"
        lines.append(
            f"| {result['evaluation_id']} · {result['case_code']} "
            f"| {result['trial']} "
            f"| {target} "
            f"| {trajectory} "
            f"| {raw} "
            f"| {explanation} "
            f"| {final} "
            f"| {'safe' if not result['hard_safety_failures'] else 'unsafe'} |"
        )
    lines.extend(
        [
            "",
            "Gold references were read only by the graders after each target run.",
            "A deterministic guard cannot convert a wrong raw model proposal into an AI-quality pass.",
            "Provider or model failures are recorded as target errors and excluded from AI-quality accuracy.",
        ]
    )
    if report["judge"]["enabled"]:
        lines.append(
            "The optional explanation judge used the configured provider; its score is reported separately."
        )
    latest_markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return timestamped_json, latest_markdown
