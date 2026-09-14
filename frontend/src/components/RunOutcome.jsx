import { formatLabel, formatQuantity } from "../lib/format";
import { ReviewPanel } from "./ReviewPanel";
import { Status } from "./Status";

function proposedAction(run) {
  const quantity = run.selected_candidate?.quantity ?? run.proposed_quantity;
  if (run.decision?.decision === "reject") return "Create no purchase order";
  if (run.decision?.decision === "investigate") return "Hold purchasing action";
  if (quantity) return `Create a purchase order for ${formatQuantity(quantity)} units`;
  return "No purchasing action proposed";
}

function executedAction(run) {
  const action = run.action;
  if (!action) {
    return run.status === "awaiting_review"
      ? "Waiting for buyer authorization"
      : "No purchase order was created";
  }
  if (action.purchase_order_id) {
    return `PO ${action.purchase_order_id} · ${formatQuantity(action.reported_quantity)} units reported by the action`;
  }
  if (action.status === "replan_required") return "Not executed because current data changed";
  return "No purchase order was created";
}

function nextRequirement(run) {
  if (run.status === "awaiting_review") {
    return "Review the exact quantity and spend, then approve or reject the purchase.";
  }

  const missingTools = run.evidence_assessment?.missing_tools ?? [];
  const staleTools = run.evidence_assessment?.stale_tools ?? [];
  if (missingTools.length) {
    return `Provide ${missingTools.map(formatLabel).join(", ")}, then run the investigation again.`;
  }
  if (staleTools.length) {
    return `Refresh ${staleTools.map(formatLabel).join(", ")}, then run the investigation again.`;
  }
  if (run.validation?.status === "failed") {
    return "Reconcile the purchase order quantity mismatch before attempting another action.";
  }
  if (run.action?.status === "replan_required") {
    return "Review the changed source data before attempting another action.";
  }
  if (run.status === "blocked" || run.status === "escalated") {
    return "Resolve the listed blocking condition, then run again with current data.";
  }
  if (run.status === "rejected") {
    return "No further action is required unless purchasing conditions change.";
  }
  if (run.status === "completed") return "No further action is required.";
  return "Wait for the current workflow to finish.";
}

function stoppingReason(run) {
  if (run.validation?.status === "failed") return run.validation.detail;
  if (run.action?.status === "replan_required") {
    return run.validation?.detail ?? formatLabel(run.action.reason_code);
  }
  return run.authorization?.detail ?? run.decision?.summary;
}

function reasonCodes(run) {
  if (run.action?.reason_code) return [run.action.reason_code];
  const source =
    run.authorization?.reason_codes?.length > 0
      ? run.authorization.reason_codes
      : (run.decision?.reason_codes ?? []);
  return [...new Set(source)];
}

export function RunOutcome({ busy, onReview, run }) {
  const needsAttention = ["awaiting_review", "blocked", "escalated"].includes(run.status);
  const reasons = reasonCodes(run);

  return (
    <>
      <section
        aria-labelledby="run-outcome-heading"
        aria-live="polite"
        className={`run-outcome${needsAttention ? " run-outcome--attention" : ""}`}
      >
        <header className="run-outcome__heading">
          <div>
            <h2 id="run-outcome-heading">Run Outcome</h2>
            <p>
              <strong>Next Required:</strong> {nextRequirement(run)}
            </p>
          </div>
          <Status value={run.status} />
        </header>

        {needsAttention ? (
          <div className="run-outcome__reason">
            <strong>
              {run.status === "awaiting_review"
                ? "Why Approval Is Required"
                : "Why the Run Stopped"}
            </strong>
            <p>{stoppingReason(run)}</p>
            {reasons.length ? (
              <ul aria-label="Run reason codes">
                {reasons.map((reason) => (
                  <li key={reason}>{formatLabel(reason)}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        <div className="run-outcome__record">
          <article>
            <span>Proposed / Executed Action</span>
            <strong>Proposed: {proposedAction(run)}</strong>
            <p>Executed: {executedAction(run)}</p>
          </article>
          <article>
            <span>Authorization</span>
            {run.authorization ? (
              <Status value={run.authorization.status} />
            ) : (
              <strong>Pending</strong>
            )}
            <p>{run.authorization?.detail ?? "Authorization has not been determined."}</p>
          </article>
          <article>
            <span>Read-Back Validation</span>
            {run.validation ? <Status value={run.validation.status} /> : <strong>Pending</strong>}
            <p>{run.validation?.detail ?? "Validation begins after an action is attempted."}</p>
            {run.validation?.expected_quantity !== null &&
            run.validation?.expected_quantity !== undefined ? (
              <small>
                Expected {formatQuantity(run.validation.expected_quantity)} · Actual{" "}
                {formatQuantity(run.validation.actual_quantity)} units
              </small>
            ) : null}
          </article>
        </div>
      </section>

      {run.status === "awaiting_review" && run.review_request ? (
        <ReviewPanel busy={busy} key={run.id} onReview={onReview} run={run} />
      ) : null}
    </>
  );
}
