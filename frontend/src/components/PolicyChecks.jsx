import { formatLabel } from "../lib/format";

export function PolicyChecks({ checks }) {
  return (
    <section className="sheet-section" aria-labelledby="policy-heading">
      <div className="section-heading">
        <div>
          <h2 id="policy-heading">Purchasing Safety</h2>
          <p>Independent business rules checked before any order can be created.</p>
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
                {check.severity === "hard"
                  ? "Required purchasing rule"
                  : check.severity === "authorization"
                    ? "Buyer approval rule"
                    : "Information only"}
              </span>
            </article>
          ))}
        </div>
      ) : (
        <div className="projection-empty">Purchasing rules appear after the agent runs.</div>
      )}
    </section>
  );
}
