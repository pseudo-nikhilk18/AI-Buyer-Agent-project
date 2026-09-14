import { formatLabel } from "../lib/format";

export function PolicyChecks({ checks }) {
  return (
    <section className="sheet-section" aria-labelledby="policy-heading">
      <div className="section-heading">
        <div>
          <h2 id="policy-heading">Policy Checks</h2>
          <p>Deterministic gates applied after the proposed decision.</p>
        </div>
      </div>

      {checks?.length ? (
        <div className="policy-list">
          {checks.map((check) => (
            <article className="policy-row" key={check.code}>
              <span
                className={
                  check.passed ? "check-mark check-mark--pass" : "check-mark check-mark--fail"
                }
                aria-hidden="true"
              >
                {check.passed ? "✓" : "!"}
              </span>
              <div>
                <h3>{formatLabel(check.code)}</h3>
                <p>{check.detail}</p>
              </div>
              <span className={`policy-row__severity policy-row__severity--${check.severity}`}>
                {formatLabel(check.severity)}
              </span>
            </article>
          ))}
        </div>
      ) : (
        <div className="projection-empty">Policy checks appear after the investigation runs.</div>
      )}
    </section>
  );
}
