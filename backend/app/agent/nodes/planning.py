import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.prompts import INVESTIGATION_SYSTEM_PROMPT
from app.agent.provider import ResolvedProvider, create_chat_model
from app.agent.state import PurchasingState, append_step
from app.domain.schemas import InvestigationPlan
from app.purchasing_tools import REQUIRED_TOOL_NAMES, TOOL_DESCRIPTIONS

logger = logging.getLogger(__name__)


def plan_investigation(
    state: PurchasingState,
    provider: ResolvedProvider | None,
) -> PurchasingState:
    if state["mode"] == "replay":
        plan = InvestigationPlan(
            tool_names=REQUIRED_TOOL_NAMES,
            summary="Collect every source required to challenge the purchase recommendation.",
        )
        return {
            "investigation_plan": plan.model_dump(mode="json"),
            "steps": append_step(state, "plan_investigation"),
        }

    try:
        model = create_chat_model(provider)
        structured_model = model.with_structured_output(InvestigationPlan)
        result = structured_model.invoke(
            [
                SystemMessage(content=INVESTIGATION_SYSTEM_PROMPT),
                HumanMessage(
                    content=json.dumps(
                        {
                            "case": state["context"],
                            "available_tools": TOOL_DESCRIPTIONS,
                        }
                    )
                ),
            ]
        )
        plan = InvestigationPlan.model_validate(result)
        return {
            "investigation_plan": plan.model_dump(mode="json"),
            "steps": append_step(state, "plan_investigation"),
        }
    except Exception:
        logger.exception("The configured model could not create an investigation plan")
        return {
            "investigation_plan": {
                "tool_names": [],
                "summary": "The configured model was unavailable, so no action was permitted.",
            },
            "error_code": "MODEL_UNAVAILABLE",
            "steps": append_step(state, "plan_investigation"),
        }
