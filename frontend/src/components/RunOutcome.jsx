import { formatCurrency, formatLabel, formatQuantity } from "../lib/format";
import { InvestigationRecord } from "./InvestigationRecord";
import { ReviewPanel } from "./ReviewPanel";
import { Status } from "./Status";

function quantityForDecision(run, decision) {
  if (!decision || decision.decision === "investigate") return null;
  if (decision.decision === "reject") return 0;
  return run?.analysis?.candidates?.find((item) => item.id === decision.candidate_id)?.quantity;
}

function decisionTitle(run, decision) {
  if (!decision) return "No decision produced";
  const quantity = quantityForDecision(run, decision);
  if (decision.decision === "accept") return `Accept ${formatQuantity(quantity)} units`;
  if (decision.decision === "modify") return `Change order to ${formatQuantity(quantity)} units`;
  if (decision.decision === "reject") return "Reject the recommendation";
  return "Investigate before purchasing";
}

function actionCopy(run) {
  if (!run) return { title: "Not attempted", detail: "The agent has not run." };
  if (run.status === "awaiting_review") {
    return {
      title: "Paused for buyer approval",
      detail: "The order is safe, but its value is above the agent's purchasing authority.",
    };
  }
  if (!run.action) {
    return {
      title: "No purchase order created",
      detail:
        run.decision?.decision === "reject"
          ? "Existing supply already covers the need."
          : "The agent stopped before any business data was changed.",
    };
  }
  if (run.action.purchase_order_id) {
    return {
      title: `Purchase order created for ${formatQuantity(run.action.reported_quantity)} units`,
      detail: "The action returned an acknowledgement and purchase-order identifier.",
    };
  }
  if (run.action.status === "replan_required") {
    return { title: "Action stopped", detail: "Source data changed before the order was written." };
  }
  return { title: "No purchase order created", detail: "No purchasing change was required." };
}

function validationCopy(run) {
  const validation = run?.validation;
  if (!validation) {
    return { title: "No result to verify", detail: "Validation follows an attempted action." };
  }
  if (validation.status === "validated") {
    return {
      title: "Created order matches the decision",
      detail: `Expected ${formatQuantity(validation.expected_quantity)} units · found ${formatQuantity(validation.actual_quantity)} units`,
    };
  }
  if (validation.status === "failed") {
    return {
      title: "Mismatch found and escalated",
      detail: `Expected ${formatQuantity(validation.expected_quantity)} units · found ${formatQuantity(validation.actual_quantity)} units`,
    };
  }
  return { title: "No purchase required validation", detail: validation.detail };
}

function evidencePayload(run, toolName, fallback) {
  return run?.evidence?.find((item) => item.tool_name === toolName)?.payload ?? fallback;
}

function forecastTotal(forecast) {
  return forecast.points.reduce((total, point) => total + point.quantity, 0);
}

function inboundTotal(openOrders) {
  return openOrders.orders.reduce((total, order) => total + order.quantity, 0);
}

function approvalLabel(status) {
  const labels = {
    auto_authorized: "No buyer approval needed",
    human_review: "Buyer approval required",
    human_approved: "Buyer approved",
    blocked: "No one — a purchasing rule blocked the action",
    not_required: "No action to approve",
    rejected: "Buyer rejected the action",
  };
  return labels[status] ?? formatLabel(status);
}

function feedbackCopy(run) {
  if (!run) {
    return {
      title: "Run the agent to start the loop",
      detail: "The resulting action will be read back, checked, and routed from there.",
    };
  }
  if (run.status === "awaiting_review") {
    return {
      title: "Buyer decision resumes the same guarded action",
      detail:
        "Approval creates and validates the exact proposed order. Rejection closes it without a write.",
    };
  }
  if (run.error_code === "MODEL_UNAVAILABLE") {
    return {
      title: "Restore model access, then run the investigation again",
      detail:
        "No purchase was made. Check the configured provider key, quota, or availability before retrying.",
    };
  }
  if (run.validation?.status === "failed") {
    return {
      title: "The mismatch is escalated for correction",
      detail:
        "The run cannot claim success or repeat the purchase until the persisted order is reconciled.",
    };
  }
  if (run.action?.status === "replan_required") {
    return {
      title: "Changed evidence returns to investigation",
      detail:
        "The agent gathers the current facts again and requires a newly guarded decision before acting.",
    };
  }
  if (run.evidence_assessment?.complete === false) {
    return {
      title: "Missing or stale evidence returns to investigation",
      detail:
        "Refresh the named source, then rerun the agent. No purchase is allowed from uncertain evidence.",
    };
  }
  if (run.status === "blocked") {
    return {
      title: "Resolve the blocking business condition, then investigate again",
      detail:
        "Budget, supplier availability, storage, or another required rule must change before a new action is considered.",
    };
  }
  if (run.decision?.decision === "reject") {
    return {
      title: "No order now; new business evidence starts another review",
      detail:
        "A future inventory, demand, or open-order change can create a new purchasing situation.",
    };
  }
  return {
    title: "Verified state closes this run",
    detail:
      "The next inventory or demand change can trigger a new purchasing situation and a fresh investigation.",
  };
}

export function RunOutcome({ busy, detail, onReview, run }) {
  const raw = run?.raw_ai_proposal;
  const decision = run?.decision;
  const action = actionCopy(run);
  const validation = validationCopy(run);
  const guardPassed = run?.decision_guard?.status === "passed";
  const inventory = evidencePayload(run, "get_inventory", detail.inventory);
  const forecast = evidencePayload(run, "get_demand_forecast", detail.forecast);
  const openOrders = evidencePayload(run, "get_open_purchase_orders", detail.open_purchase_orders);
  const budget = evidencePayload(run, "get_budget", detail.budget);
  const feedback = feedbackCopy(run);
  const proposalLabel =
    run?.error_code === "MODEL_UNAVAILABLE"
      ? "AI response unavailable"
      : run?.mode === "live"
        ? "AI response after investigation"
        : "Replay proposal";

  return (
    <ol className="result-flow" aria-label="Purchasing agent result">
      <li className="result-step">
        <div className="result-step__number">1</div>
        <div className="result-step__body">
          <header>
            <p>Purchasing situation</p>
            <h2>Should the company order {formatQuantity(detail.recommended_quantity)} units?</h2>
          </header>
          <dl className="situation-facts">
            <div>
              <dt>Product</dt>
              <dd>{detail.product_name}</dd>
            </div>
            <div>
              <dt>Fulfillment node</dt>
              <dd>{detail.node_name}</dd>
            </div>
            <div>
              <dt>On hand</dt>
              <dd>{formatQuantity(inventory.on_hand_quantity)} units</dd>
            </div>
            <div>
              <dt>Forecast</dt>
              <dd>{formatQuantity(forecastTotal(forecast))} units</dd>
            </div>
            <div>
              <dt>Already incoming</dt>
              <dd>{formatQuantity(inboundTotal(openOrders))} units</dd>
            </div>
            <div>
              <dt>Available budget</dt>
              <dd>{formatCurrency(budget.available_minor, budget.currency)}</dd>
            </div>
          </dl>
        </div>
      </li>

      <li className="result-step">
        <div className="result-step__number">2</div>
        <div className="result-step__body">
          <header>
            <p>Information investigated</p>
            <h2>The agent chose the evidence it needed and explained why</h2>
          </header>
          <p className="step-copy">
            {run?.error_code === "MODEL_UNAVAILABLE"
              ? "The configured AI model was unavailable, so it could not select evidence tools. The workflow stopped without changing purchasing data."
              : run?.mode === "live"
                ? "The AI selected from the approved tool catalog. The workflow then executed those SQL-backed tools and recorded the returned evidence."
                : "The engineering replay used the required tool plan. The workflow executed the same SQL-backed tools and recorded the returned evidence."}
          </p>
          <InvestigationRecord run={run} />
        </div>
      </li>

      <li className="result-step">
        <div className="result-step__number">3</div>
        <div className="result-step__body">
          <header>
            <p>Agent decision</p>
            <h2>{decisionTitle(run, decision)}</h2>
          </header>
          <div className="decision-comparison">
            <div>
              <span>{proposalLabel}</span>
              <strong>
                {raw
                  ? decisionTitle(run, raw)
                  : run?.evidence_assessment?.complete === false
                    ? run?.error_code === "MODEL_UNAVAILABLE"
                      ? "Configured AI model unavailable"
                      : "No purchase proposed without trustworthy evidence"
                    : run?.mode === "replay"
                      ? "Replay does not call an AI model"
                      : "No usable proposal returned"}
              </strong>
              <p>{raw?.summary ?? decision?.summary}</p>
              {raw?.reason_codes?.length ? (
                <ul className="reason-list" aria-label="AI response reasons">
                  {raw.reason_codes.map((reason) => (
                    <li key={reason}>{formatLabel(reason)}</li>
                  ))}
                </ul>
              ) : null}
            </div>
            <div>
              <span>Independent safety check</span>
              <strong>
                {guardPassed ? "Decision verified as safe" : "Unsafe action prevented"}
              </strong>
              <p>{run?.decision_guard?.detail ?? "Waiting for the agent decision."}</p>
            </div>
          </div>
          {run?.authorization ? (
            <p className="authority-line">
              <strong>Approval:</strong> {approvalLabel(run.authorization.status)}
            </p>
          ) : null}
        </div>
      </li>

      <li className="result-step">
        <div className="result-step__number">4</div>
        <div className="result-step__body">
          <header>
            <p>Action taken</p>
            <h2>{action.title}</h2>
          </header>
          <p className="step-copy">{action.detail}</p>
          {run?.proposed_spend_minor !== null && run?.proposed_spend_minor !== undefined ? (
            <p className="action-amount">
              Proposed spend: {formatCurrency(run.proposed_spend_minor, detail.supplier.currency)}
            </p>
          ) : null}
          {run?.status === "awaiting_review" && run.review_request ? (
            <ReviewPanel busy={busy} onReview={onReview} run={run} />
          ) : null}
        </div>
      </li>

      <li className="result-step">
        <div className="result-step__number">5</div>
        <div className="result-step__body">
          <header className="validation-heading">
            <div>
              <p>Result validation</p>
              <h2>{validation.title}</h2>
            </div>
            {run?.validation ? <Status value={run.validation.status} /> : null}
          </header>
          <p className="step-copy">{validation.detail}</p>
          <div className="feedback-loop">
            <span>Feedback loop</span>
            <strong>{feedback.title}</strong>
            <p>{feedback.detail}</p>
            <div aria-label="Validation feedback path">
              <span>Validate actual result</span>
              <b aria-hidden="true">→</b>
              <span>Complete, reinvestigate, or escalate</span>
            </div>
          </div>
        </div>
      </li>
    </ol>
  );
}
