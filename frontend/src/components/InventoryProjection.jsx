import { formatDate, formatQuantity } from "../lib/format";

function chartGeometry(points, safetyStock) {
  const closings = points.map((point) => point.closing_quantity);
  const minimum = Math.min(0, safetyStock, ...closings);
  const maximum = Math.max(1, safetyStock, ...closings);
  const range = maximum - minimum || 1;
  const left = 24;
  const right = 776;
  const top = 20;
  const bottom = 172;
  const xStep = points.length > 1 ? (right - left) / (points.length - 1) : 0;
  const y = (value) => bottom - ((value - minimum) / range) * (bottom - top);

  return {
    polyline: points
      .map((point, index) => `${left + index * xStep},${y(point.closing_quantity)}`)
      .join(" "),
    zeroY: y(0),
    safetyY: y(safetyStock),
    pointPositions: points.map((point, index) => ({
      x: left + index * xStep,
      y: y(point.closing_quantity),
      point,
    })),
  };
}

export function InventoryProjection({ candidate }) {
  if (!candidate?.projection?.length) {
    return (
      <section className="sheet-section" aria-labelledby="projection-heading">
        <div className="section-heading">
          <div>
            <h2 id="projection-heading">Inventory Path</h2>
            <p>Run the investigation to calculate the day-by-day stock position.</p>
          </div>
        </div>
        <div className="projection-empty">No projection has been calculated for this case.</div>
      </section>
    );
  }

  const geometry = chartGeometry(candidate.projection, candidate.safety_stock_quantity);

  return (
    <section className="sheet-section" aria-labelledby="projection-heading">
      <div className="section-heading">
        <div>
          <h2 id="projection-heading">Inventory Path</h2>
          <p>Projected closing stock after incoming orders and daily demand.</p>
        </div>
        <div className="projection-summary">
          <span>Minimum</span>
          <strong>{formatQuantity(candidate.projected_minimum_quantity)} units</strong>
        </div>
      </div>

      <div className="inventory-chart" role="img" aria-label="Projected closing inventory by day">
        <svg aria-hidden="true" viewBox="0 0 800 210" preserveAspectRatio="none">
          <line className="chart-zero" x1="24" x2="776" y1={geometry.zeroY} y2={geometry.zeroY} />
          <line
            className="chart-safety"
            x1="24"
            x2="776"
            y1={geometry.safetyY}
            y2={geometry.safetyY}
          />
          <polyline className="chart-path" points={geometry.polyline} />
          {geometry.pointPositions.map(({ x, y, point }) => (
            <circle className="chart-point" cx={x} cy={y} key={point.date} r="5">
              <title>
                {formatDate(point.date)}: {formatQuantity(point.closing_quantity)} units
              </title>
            </circle>
          ))}
        </svg>
        <div className="chart-key">
          <span>
            <i aria-hidden="true" className="chart-key__line" /> Closing stock
          </span>
          <span>
            <i aria-hidden="true" className="chart-key__line chart-key__line--safety" /> Safety
            stock {formatQuantity(candidate.safety_stock_quantity)}
          </span>
        </div>
      </div>

      <div className="projection-table-wrap">
        <table className="projection-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Opening</th>
              <th>Incoming</th>
              <th>Demand</th>
              <th>Closing</th>
            </tr>
          </thead>
          <tbody>
            {candidate.projection.map((point) => (
              <tr key={point.date}>
                <th>{formatDate(point.date)}</th>
                <td>{formatQuantity(point.opening_quantity)}</td>
                <td>{formatQuantity(point.incoming_quantity)}</td>
                <td>{formatQuantity(point.demand_quantity)}</td>
                <td data-negative={point.closing_quantity < 0}>
                  {formatQuantity(point.closing_quantity)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
