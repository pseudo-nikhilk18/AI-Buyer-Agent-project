import { formatQuantity } from "../lib/format";
import { getScenarioPresentation, SCENARIO_GROUPS } from "../lib/scenarios";
import { Status } from "./Status";

export function CaseQueue({ busy, cases, selectedId, onSelect }) {
  return (
    <aside className="case-rail" aria-labelledby="queue-heading">
      <div className="case-rail__heading">
        <div>
          <p className="case-rail__title" id="queue-heading">
            Demo Scenarios
          </p>
          <p>{cases.length} controlled situations · 1 buyer agent</p>
        </div>
      </div>

      <nav aria-label="Demo scenarios" className="case-list">
        {SCENARIO_GROUPS.map((group) => {
          const groupCases = cases.filter(group.includes);
          if (!groupCases.length) return null;

          return (
            <section className="scenario-group" key={group.key}>
              <div className="scenario-group__heading">
                <p className="scenario-group__title">{group.label}</p>
                <p>{group.description}</p>
              </div>
              {groupCases.map((item) => {
                const isSelected = item.id === selectedId;
                const presentation = getScenarioPresentation(item);
                return (
                  <a
                    aria-current={isSelected ? "page" : undefined}
                    aria-disabled={busy || undefined}
                    className="case-row"
                    data-selected={isSelected}
                    href={`?case=${encodeURIComponent(item.id)}`}
                    key={item.id}
                    onClick={(event) => {
                      if (busy) {
                        event.preventDefault();
                        return;
                      }
                      if (!(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)) {
                        event.preventDefault();
                        onSelect(item.id);
                      }
                    }}
                  >
                    <span className="case-row__topline">
                      <strong>{presentation.label}</strong>
                      <Status value={item.latest_run_status ?? item.status} />
                    </span>
                    <span className="case-row__meta">
                      {formatQuantity(item.recommended_quantity)}-unit recommendation
                    </span>
                  </a>
                );
              })}
            </section>
          );
        })}
      </nav>
    </aside>
  );
}
