export function SystemOverview() {
  return (
    <section className="system-overview" aria-labelledby="system-heading">
      <div className="system-overview__copy">
        <p>One Buyer Agent</p>
        <h1 id="system-heading">One Recommendation. One Controlled Purchasing Decision.</h1>
        <p>
          The agent helps a quick-commerce buyer protect product availability without adding
          avoidable purchasing loss.
        </p>
      </div>

      <div className="business-relationship" aria-label="Purchasing business relationship">
        <div className="relationship-party">
          <strong>Customers</strong>
          <span>Create local demand</span>
        </div>
        <span className="relationship-link">demand</span>
        <div className="company-boundary">
          <span>Quick-Commerce Company</span>
          <div>
            <p>
              <strong>Fulfillment Node</strong>
              <span>Holds stock and serves orders</span>
            </p>
            <p>
              <strong>Buyer + Agent</strong>
              <span>Controls replenishment</span>
            </p>
          </div>
        </div>
        <span className="relationship-link">approved PO</span>
        <div className="relationship-party">
          <strong>Supplier</strong>
          <span>Replenishes the node</span>
        </div>
      </div>
    </section>
  );
}
