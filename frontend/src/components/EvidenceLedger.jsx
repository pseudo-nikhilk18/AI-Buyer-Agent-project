import { evidenceSummary, formatDate, formatLabel } from "../lib/format";

const TOOL_ORDER = [
  "get_inventory",
  "get_demand_forecast",
  "get_open_purchase_orders",
  "get_supplier_terms",
  "get_budget",
  "get_storage_capacity",
];

function currentEvidence(detail) {
  const stale = new Set(detail.evidence_assessment.stale_tools);
  return [
    ["get_inventory", detail.inventory],
    ["get_demand_forecast", detail.forecast],
    ["get_open_purchase_orders", detail.open_purchase_orders],
    ["get_supplier_terms", detail.supplier],
    ["get_budget", detail.budget],
    ["get_storage_capacity", detail.storage_capacity],
  ].map(([toolName, payload]) => ({
    tool_name: toolName,
    payload,
    observed_at: payload.observed_at,
    is_fresh: !stale.has(toolName),
  }));
}

export function EvidenceLedger({ detail, run }) {
  const records = run?.evidence?.length ? run.evidence : currentEvidence(detail);
  const orderedRecords = [...records].sort(
    (a, b) => TOOL_ORDER.indexOf(a.tool_name) - TOOL_ORDER.indexOf(b.tool_name),
  );
  const assessment = run?.evidence_assessment ?? detail.evidence_assessment;

  return (
    <section className="sheet-section" aria-labelledby="evidence-heading">
      <div className="section-heading">
        <div>
          <h2 id="evidence-heading">Decision Evidence</h2>
          <p>Inputs used to verify need, supply, cost, and capacity.</p>
        </div>
        <span
          className={
            assessment.complete ? "freshness freshness--fresh" : "freshness freshness--stale"
          }
        >
          {assessment.complete ? "Evidence ready" : "Evidence needs attention"}
        </span>
      </div>

      <div className="evidence-ledger">
        {orderedRecords.map((record) => {
          const summary = evidenceSummary(record.tool_name, record.payload);
          return (
            <article className="evidence-row" key={record.tool_name}>
              <div>
                <h3>{formatLabel(record.tool_name)}</h3>
                <p>{summary.detail}</p>
              </div>
              <strong>{summary.value}</strong>
              <div className="evidence-row__freshness">
                <span
                  className={
                    record.is_fresh ? "fresh-dot fresh-dot--yes" : "fresh-dot fresh-dot--no"
                  }
                >
                  {record.is_fresh ? "Fresh" : "Stale"}
                </span>
                <time dateTime={record.observed_at}>{formatDate(record.observed_at, true)}</time>
              </div>
            </article>
          );
        })}
      </div>

      {assessment.reason_codes.length > 0 ? (
        <p className="evidence-note">{assessment.reason_codes.map(formatLabel).join(". ")}.</p>
      ) : null}
    </section>
  );
}
