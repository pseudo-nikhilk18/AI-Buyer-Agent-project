import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.agent.provider import ResolvedProvider, create_chat_model
from app.evals.dataset import EvaluationExample


class ExplanationJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_grounding: int = Field(ge=1, le=5)
    decision_quality: int = Field(ge=1, le=5)
    risk_awareness: int = Field(ge=1, le=5)
    buyer_clarity: int = Field(ge=1, le=5)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=5)
    rationale: str = Field(min_length=1, max_length=500)


JUDGE_PROMPT = """
You are grading a purchasing agent's short decision explanation after its run has finished.
The reference answer below is evaluator-only. Score only the explanation, not the safety
guard. Use 1 (poor) to 5 (excellent) for: evidence grounding, decision quality, awareness
of loss and operational risk, and clarity for a retail buyer. List concrete unsupported
claims. Do not reward verbosity, hidden chain-of-thought, or merely matching wording.
Return only the requested structured result.
""".strip()


def judge_explanation(
    *,
    provider: ResolvedProvider,
    example: EvaluationExample,
    state: dict,
) -> dict:
    raw = state.get("raw_ai_proposal") or state.get("decision") or {}
    payload = {
        "purchasing_input": {
            "recommended_quantity": example.input.recommended_quantity,
            "product": example.input.product.model_dump(),
            "supplier_terms": example.input.supplier_terms.model_dump(),
            "inventory": example.input.inventory.model_dump(),
            "forecast": example.input.forecast.model_dump(),
            "inbound_order": (
                example.input.inbound_order.model_dump()
                if example.input.inbound_order
                else None
            ),
            "supplier_available_quantity": example.input.supplier_available_quantity,
            "budget_minor": example.input.budget_minor,
            "storage_capacity_quantity": example.input.storage_capacity_quantity,
        },
        "reference_outcome": example.reference.model_dump(),
        "agent_explanation": {
            "decision": raw.get("decision"),
            "candidate_id": raw.get("candidate_id"),
            "reason_codes": raw.get("reason_codes", []),
            "summary": raw.get("summary"),
        },
    }
    model = create_chat_model(provider).with_structured_output(ExplanationJudgment)
    result = ExplanationJudgment.model_validate(
        model.invoke(
            [
                SystemMessage(content=JUDGE_PROMPT),
                HumanMessage(content=json.dumps(payload)),
            ]
        )
    )
    scores = [
        result.evidence_grounding,
        result.decision_quality,
        result.risk_awareness,
        result.buyer_clarity,
    ]
    report = result.model_dump()
    report["mean_score"] = round(sum(scores) / len(scores), 2)
    report["passed"] = report["mean_score"] >= 4 and not result.unsupported_claims
    return report
