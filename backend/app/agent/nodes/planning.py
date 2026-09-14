import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.prompts import INVESTIGATION_SYSTEM_PROMPT
from app.agent.provider import ResolvedProvider, create_chat_model
from app.agent.state import PurchasingState, append_step
from app.domain.schemas import (
    InvestigationAttempt,
    InvestigationPlan,
    InvestigationToolRequest,
)
from app.purchasing_tools import REQUIRED_TOOL_NAMES, TOOL_DESCRIPTIONS

logger = logging.getLogger(__name__)


REPLAY_INVESTIGATION = {
    "get_inventory": (
        "Establish the usable stock available at the fulfillment node.",
        ["How much inventory is sellable after reservations and damage?"],
    ),
    "get_demand_forecast": (
        "Measure demand across the replenishment and safety-stock horizon.",
        [
            "What demand must inventory and inbound supply cover?",
            "How current is the forecast?",
        ],
    ),
    "get_open_purchase_orders": (
        "Account for supply already committed before proposing another order.",
        ["What quantities are already inbound, and when will they arrive?"],
    ),
    "get_supplier_terms": (
        "Check commercial, timing, availability, and supplier eligibility constraints.",
        ["What quantity can the supplier deliver under its MOQ, pack, and lead-time terms?"],
    ),
    "get_budget": (
        "Confirm the purchase fits the remaining purchasing budget.",
        ["What spend is currently available for this purchase?"],
    ),
    "get_storage_capacity": (
        "Confirm the proposed inbound quantity can be stored safely.",
        ["How many additional units can the node receive?"],
    ),
}


def _operational_context(state: PurchasingState) -> dict:
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


def build_investigation_prompt_payload(state: PurchasingState) -> dict:
    assessment = state.get("evidence_assessment", {})
    collected = {
        name: payload
        for name, payload in state.get("evidence", {}).items()
        if "error" not in payload
    }
    payload = {
        "operational_context": _operational_context(state),
        "available_tools": TOOL_DESCRIPTIONS,
    }
    if state.get("investigation_attempts", 0):
        payload["missing_required_sources"] = assessment.get("missing_tools", [])
        payload["already_collected_evidence"] = collected
    return payload


def replay_investigation_plan() -> InvestigationPlan:
    return InvestigationPlan(
        tool_requests=[
            InvestigationToolRequest(
                tool_name=tool_name,
                purpose=REPLAY_INVESTIGATION[tool_name][0],
                questions=REPLAY_INVESTIGATION[tool_name][1],
            )
            for tool_name in REQUIRED_TOOL_NAMES
        ],
        summary=(
            "Verify need, inbound supply, supplier constraints, budget, and capacity "
            "before acting."
        ),
    )


def plan_investigation(
    state: PurchasingState,
    provider: ResolvedProvider | None,
) -> PurchasingState:
    attempt_number = state.get("investigation_attempts", 0) + 1
    missing_before = state.get("evidence_assessment", {}).get("missing_tools", [])
    if state["mode"] == "replay":
        plan = replay_investigation_plan()
        error_code = None
    else:
        try:
            model = create_chat_model(provider)
            structured_model = model.with_structured_output(InvestigationPlan)
            result = structured_model.invoke(
                [
                    SystemMessage(content=INVESTIGATION_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(build_investigation_prompt_payload(state))),
                ]
            )
            plan = InvestigationPlan.model_validate(result)
            error_code = None
        except Exception:
            logger.exception("The configured model could not create an investigation plan")
            plan = InvestigationPlan(
                tool_requests=[],
                summary="The configured model was unavailable, so no action was permitted.",
            )
            error_code = "MODEL_UNAVAILABLE"

    record = InvestigationAttempt(
        attempt=attempt_number,
        missing_sources_before=missing_before,
        plan=plan,
    )
    return {
        "investigation_plan": plan.model_dump(mode="json"),
        "investigation_history": [
            *state.get("investigation_history", []),
            record.model_dump(mode="json"),
        ],
        "investigation_attempts": attempt_number,
        "error_code": error_code,
        "steps": append_step(state, "plan_investigation"),
    }
