from datetime import UTC, datetime, timedelta

from app.domain.schemas import CaseContext, EvidenceAssessment
from app.purchasing_tools import REQUIRED_TOOL_NAMES


def parse_observed_at(payload: dict) -> datetime | None:
    value = payload.get("observed_at")
    if not isinstance(value, str):
        return None
    try:
        observed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed_at.tzinfo is None:
        return observed_at.replace(tzinfo=UTC)
    return observed_at


def assess_evidence(
    *,
    context: CaseContext,
    evidence: dict[str, dict],
    checked_at: datetime | None = None,
) -> EvidenceAssessment:
    now = checked_at or datetime.now(UTC)
    missing_tools = [
        name
        for name in REQUIRED_TOOL_NAMES
        if name not in evidence or "error" in evidence[name]
    ]
    stale_tools: list[str] = []
    limits = {
        "get_inventory": timedelta(minutes=context.inventory_freshness_minutes),
        "get_demand_forecast": timedelta(hours=context.forecast_freshness_hours),
        "get_open_purchase_orders": timedelta(minutes=context.inventory_freshness_minutes),
        "get_supplier_terms": timedelta(minutes=context.supplier_freshness_minutes),
        "get_budget": timedelta(minutes=context.constraint_freshness_minutes),
        "get_storage_capacity": timedelta(minutes=context.constraint_freshness_minutes),
    }

    for tool_name, limit in limits.items():
        payload = evidence.get(tool_name)
        if payload is None or "error" in payload:
            continue
        observed_at = parse_observed_at(payload)
        if observed_at is None or now - observed_at > limit:
            stale_tools.append(tool_name)

    forecast_payload = evidence.get("get_demand_forecast", {})
    supplier_payload = evidence.get("get_supplier_terms", {})
    points = forecast_payload.get("points", [])
    lead_time = supplier_payload.get("lead_time_days")
    if isinstance(lead_time, int):
        required_days = lead_time + context.review_period_days
        if len(points) < required_days and "get_demand_forecast" not in missing_tools:
            missing_tools.append("get_demand_forecast")

    reason_codes = [f"missing:{name}" for name in missing_tools]
    reason_codes.extend(f"stale:{name}" for name in stale_tools)
    return EvidenceAssessment(
        complete=not missing_tools and not stale_tools,
        missing_tools=missing_tools,
        stale_tools=stale_tools,
        reason_codes=reason_codes,
    )
