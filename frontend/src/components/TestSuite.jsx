import { formatLabel, formatQuantity } from "../lib/format";
import { Status } from "./Status";

export function TestSuite({ busyCaseId, cases, onRun, onView, selectedId }) {
  return (
    <section aria-labelledby="test-suite-heading" className="test-suite">
      <div className="test-suite__heading">
        <div>
          <h1 id="test-suite-heading">Run Agent Tests</h1>
        </div>
        <p>
          Each test gives the purchasing agent a recommendation and live business facts. The result
          shows what it investigated, decided, changed, and verified.
        </p>
      </div>

      <div className="test-grid">
        {cases.map((item, index) => {
          const isRunning = busyCaseId === item.id;
          const hasResult = Boolean(item.latest_run_status);
          return (
            <article className="test-card" data-selected={selectedId === item.id} key={item.id}>
              <div className="test-card__topline">
                <span>Test {String(index + 1).padStart(2, "0")}</span>
                <Status value={isRunning ? "running" : (item.latest_run_status ?? "ready")} />
              </div>
              <div>
                <h2>{item.title}</h2>
                <p>{item.test_purpose}</p>
              </div>
              <dl className="test-card__facts">
                <div>
                  <dt>Recommendation</dt>
                  <dd>{formatQuantity(item.recommended_quantity)} units</dd>
                </div>
                <div>
                  <dt>Checks</dt>
                  <dd>{item.test_dimensions.slice(0, 2).map(formatLabel).join(" · ")}</dd>
                </div>
              </dl>
              <div className="test-card__actions">
                <button
                  className="button button--primary"
                  disabled={Boolean(busyCaseId)}
                  onClick={() => onRun(item)}
                  type="button"
                >
                  {isRunning ? "Agent running…" : hasResult ? "Run again" : "Run test"}
                </button>
                {hasResult ? (
                  <button
                    className="button button--quiet"
                    disabled={Boolean(busyCaseId)}
                    onClick={() => onView(item.id)}
                    type="button"
                  >
                    View result
                  </button>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
