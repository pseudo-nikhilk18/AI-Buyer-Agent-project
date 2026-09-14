import { formatLabel, formatQuantity } from "../lib/format";
import { Status } from "./Status";

const STEP_LABELS = {
  plan_investigation: "Plan investigation",
  gather_evidence: "Gather current evidence",
  assess_evidence: "Assess evidence quality",
  calculate_requirement: "Calculate safe requirement",
  propose_decision: "Propose decision",
  validate_plan: "Validate against policy",
  authorize_action: "Apply authority limits",
  execute_action: "Create purchase order",
  validate_outcome: "Read back and validate",
  finalize: "Close workflow",
};

export function WorkflowTimeline({ run }) {
  return (
    <section className="sheet-section" aria-labelledby="workflow-heading">
      <div className="section-heading">
        <div>
          <h2 id="workflow-heading">Workflow Record</h2>
          <p>Every completed step, action receipt, and independent validation.</p>
        </div>
        {run ? <Status value={run.status} /> : null}
      </div>

      {run?.steps?.length ? (
        <ol className="workflow-list">
          {run.steps.map((step, index) => (
            <li key={`${step}-${index}`}>
              <span>{index + 1}</span>
              <p>{STEP_LABELS[step] ?? formatLabel(step)}</p>
            </li>
          ))}
        </ol>
      ) : (
        <div className="projection-empty">
          The workflow trace begins when the investigation runs.
        </div>
      )}

      {run?.action ? (
        <div className="outcome-strip">
          <div>
            <span>Action</span>
            <strong>{formatLabel(run.action.status)}</strong>
            <p>
              {run.action.purchase_order_id
                ? `Purchase order ${run.action.purchase_order_id}`
                : "No purchase order was created."}
            </p>
          </div>
          <div>
            <span>Requested</span>
            <strong>{formatQuantity(run.action.requested_quantity)} units</strong>
            <p>Reported: {formatQuantity(run.action.reported_quantity)} units</p>
          </div>
          <div>
            <span>Read-back validation</span>
            <strong>
              <Status value={run.validation?.status ?? "not_required"} />
            </strong>
            <p>{run.validation?.detail ?? "No validation was required."}</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
