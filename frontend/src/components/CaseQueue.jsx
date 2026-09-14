import { formatLabel, formatQuantity } from "../lib/format";
import { Status } from "./Status";

export function CaseQueue({ busy, cases, selectedId, onSelect }) {
  return (
    <aside className="case-rail" aria-labelledby="queue-heading">
      <div className="case-rail__heading">
        <div>
          <p className="case-rail__title" id="queue-heading">
            Review Queue
          </p>
          <p>{cases.length} purchasing cases</p>
        </div>
      </div>

      <nav aria-label="Purchasing cases" className="case-list">
        {cases.map((item) => {
          const isSelected = item.id === selectedId;
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
                <span className="case-row__code">{item.code}</span>
                <Status value={item.latest_run_status ?? item.status} />
              </span>
              <strong>{item.title}</strong>
              <span className="case-row__meta">
                {formatLabel(item.scenario_type)} · {formatQuantity(item.recommended_quantity)}{" "}
                units
              </span>
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
