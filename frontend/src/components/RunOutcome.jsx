import { formatCurrency, formatLabel, formatQuantity } from "../lib/format";
import { ReviewPanel } from "./ReviewPanel";
import { Status } from "./Status";

function proposalQuantity(run, draft) {
  if (!draft || draft.decision === "investigate") return null;
  if (draft.decision === "reject") return 0;
  const candidate = run?.analysis?.candidates?.find((item) => item.id === draft.candidate_id);
  return candidate?.quantity ?? null;
}

function decisionLabel(run, draft) {
  if (!draft) return "Not Evaluated";
  const quantity = proposalQuantity(run, draft);
  if (draft.decision === "accept") return `Accept ${formatQuantity(quantity)} Units`;
  if (draft.decision === "modify") return `Modify to ${formatQuantity(quantity)} Units`;
  if (draft.decision === "reject") return "Reject the Order";
  return "Investigate Before Acting";
}

function aiProposal(run) {
  if (!run) {
    return { title: "Not Evaluated", detail: "Starts after the evidence investigation" };
  }
  if (run.raw_ai_proposal) {
    return {
      title: decisionLabel(run, run.raw_ai_proposal),
      detail: run.raw_ai_proposal.summary,
    };
  }
  if (run.mode === "replay") {
    return {
      title: "No Live Model Call",
      detail: "Replay verifies the deterministic workflow and safety controls only",
    };
  }
  return {
    title: "No Purchase Proposed",
    detail:
      run.evidence_assessment?.complete === false
        ? "The evidence gate stopped the decision before a purchase could be proposed"
        : "The live model did not return a usable proposal",
  };
}

function safetyDecision(run) {
  if (!run?.decision) {
    return { title: "Pending", detail: "Checks the proposal against the loss-bounded policy" };
  }
  return {
    title: decisionLabel(run, run.decision),
    detail: run.decision_guard?.detail ?? run.authorization?.detail ?? run.decision.summary,
  };
}

function executedAction(run) {
  if (!run) return { title: "Not Attempted", detail: "Runs only after safety authorization" };
  const action = run.action;
  if (!action) {
    return {
      title: run.status === "awaiting_review" ? "Waiting for Buyer" : "No Order Created",
      detail:
        run.status === "awaiting_review"
          ? "The exact action is paused for approval"
          : "The workflow stopped before a purchasing mutation",
    };
  }
  if (action.purchase_order_id) {
    return {
      title: "Purchase Order Created",
      detail: `${formatQuantity(action.reported_quantity)} units reported by the action`,
    };
  }
  if (action.status === "replan_required") {
    return { title: "Action Stopped", detail: "Current data changed before execution" };
  }
  return { title: "No Order Created", detail: "No purchasing mutation was required" };
}

function verifiedOutcome(run) {
  if (!run?.validation) {
    return { status: null, detail: "Read-back starts after an action is attempted" };
  }
  const validation = run.validation;
  const hasQuantity = validation.expected_quantity !== null;
  return {
    status: validation.status,
    detail: hasQuantity
      ? `Expected ${formatQuantity(validation.expected_quantity)} · Actual ${formatQuantity(validation.actual_quantity)} units`
      : validation.detail,
  };
}

function nextRequirement(run) {
  if (!run) return "Run the buyer agent against the current evidence.";
  if (run.status === "awaiting_review") {
    return "Review the exact quantity and spend, then approve or reject the purchase.";
  }

  const missingTools = run.evidence_assessment?.missing_tools ?? [];
  const staleTools = run.evidence_assessment?.stale_tools ?? [];
  if (missingTools.length) {
    return `Provide ${missingTools.map(formatLabel).join(", ")}, then run again.`;
  }
  if (staleTools.length) {
    return `Refresh ${staleTools.map(formatLabel).join(", ")}, then run again.`;
  }
  if (run.validation?.status === "failed") {
    return "Reconcile the recorded purchase-order quantity before attempting another action.";
  }
  if (run.action?.status === "replan_required") {
    return "Review the changed source data before attempting another action.";
  }
  if (run.status === "blocked" || run.status === "escalated") {
    return "Resolve the listed blocking condition, then run again with current evidence.";
  }
  if (run.status === "rejected") {
    return "No action is required unless purchasing conditions change.";
  }
  if (run.status === "completed") return "No further action is required.";
  return "Wait for the current workflow to finish.";
}

function stoppingReason(run) {
  if (run?.validation?.status === "failed") return run.validation.detail;
  if (run?.action?.status === "replan_required") {
    return run.validation?.detail ?? formatLabel(run.action.reason_code);
  }
  return run?.authorization?.detail ?? run?.decision?.summary;
}

function reasonCodes(run) {
  if (run?.action?.reason_code) return [run.action.reason_code];
  const source =
    run?.authorization?.reason_codes?.length > 0
      ? run.authorization.reason_codes
      : (run?.decision?.reason_codes ?? []);
  return [...new Set(source)];
}

function stageState(isComplete, isNext) {
  if (isComplete) return "complete";
  if (isNext) return "current";
  return "pending";
}

export function RunOutcome({ busy, detail, onReview, run }) {
  const rawProposal = aiProposal(run);
  const guardedDecision = safetyDecision(run);
  const action = executedAction(run);
  const outcome = verifiedOutcome(run);
  const needsAttention = ["awaiting_review", "blocked", "escalated"].includes(run?.status);
  const reasons = reasonCodes(run);
  const evidenceComplete = Boolean(run?.evidence_assessment);
  const proposalComplete = Boolean(run?.decision);
  const safetyComplete = Boolean(run?.authorization);
  const actionComplete =
    Boolean(run?.action) || ["blocked", "rejected", "completed"].includes(run?.status);
  const outcomeComplete = Boolean(run?.validation);

  return (
    <>
      <section
        className="decision-journey"
        aria-labelledby="decision-journey-heading"
        aria-live="polite"
      >
        <header className="decision-journey__heading">
          <div>
            <h2 id="decision-journey-heading">One Controlled Decision</h2>
            <p>
              Recommendation through verified outcome, with deterministic safeguards between each
              step.
            </p>
          </div>
          {run ? <Status value={run.status} /> : <Status value="ready" />}
        </header>

        <ol className="decision-journey__stages">
          <li data-state="complete">
            <span>1 · Recommendation</span>
            <strong>{formatQuantity(detail.recommended_quantity)} Units</strong>
            <p>Submitted for review</p>
          </li>
          <li data-state={stageState(proposalComplete, !run || evidenceComplete)}>
            <span>2 · AI Proposal</span>
            <strong>{rawProposal.title}</strong>
            <p>{rawProposal.detail}</p>
          </li>
          <li data-state={stageState(safetyComplete, proposalComplete)}>
            <span>3 · Safety Decision</span>
            <strong>{guardedDecision.title}</strong>
            {run?.decision_guard ? <Status value={run.decision_guard.status} /> : null}
            <p>{guardedDecision.detail}</p>
          </li>
          <li data-state={stageState(actionComplete, safetyComplete)}>
            <span>4 · Authorized Action</span>
            {run?.authorization ? (
              <Status value={run.authorization.status} />
            ) : (
              <strong>Pending</strong>
            )}
            <p>
              {run?.proposed_spend_minor !== null && run?.proposed_spend_minor !== undefined
                ? `${formatCurrency(run.proposed_spend_minor, detail.supplier.currency)} proposed spend`
                : "Checks constraints and purchasing authority"}
            </p>
            <strong>{action.title}</strong>
            <p>{action.detail}</p>
          </li>
          <li data-state={stageState(outcomeComplete, actionComplete)}>
            <span>5 · Verified Outcome</span>
            {outcome.status ? <Status value={outcome.status} /> : <strong>Pending</strong>}
            <p>{outcome.detail}</p>
          </li>
        </ol>

        {needsAttention ? (
          <div className="decision-attention">
            <div>
              <strong>
                {run.status === "awaiting_review"
                  ? "Why Buyer Approval Is Required"
                  : "Why the Agent Stopped"}
              </strong>
              <p>{stoppingReason(run)}</p>
            </div>
            {reasons.length ? (
              <ul aria-label="Run reason codes">
                {reasons.map((reason) => (
                  <li key={reason}>{formatLabel(reason)}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        <div className="decision-next">
          <strong>Next Required</strong>
          <p>{nextRequirement(run)}</p>
        </div>
      </section>

      {run?.status === "awaiting_review" && run.review_request ? (
        <ReviewPanel busy={busy} key={run.id} onReview={onReview} run={run} />
      ) : null}
    </>
  );
}
