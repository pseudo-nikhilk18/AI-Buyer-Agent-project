import { useState } from "react";

import { formatCurrency, formatQuantity } from "../lib/format";

export function ReviewPanel({ run, busy, onReview }) {
  const [note, setNote] = useState("");
  const [confirmingReject, setConfirmingReject] = useState(false);
  const request = run.review_request;

  if (!request) return null;

  return (
    <section className="review-panel" aria-labelledby="review-heading">
      <div>
        <h3 id="review-heading">Buyer approval needed</h3>
        <p>{request.decision.summary}</p>
      </div>
      <dl>
        <div>
          <dt>Purchase quantity</dt>
          <dd>{formatQuantity(request.proposed_quantity)} units</dd>
        </div>
        <div>
          <dt>Committed spend</dt>
          <dd>{formatCurrency(request.proposed_spend_minor, request.currency)}</dd>
        </div>
      </dl>
      <label htmlFor="review-note">
        Decision note <span>(optional)</span>
      </label>
      <textarea
        autoComplete="off"
        id="review-note"
        maxLength={400}
        name="review-note"
        onChange={(event) => setNote(event.target.value)}
        placeholder="Add context for this decision…"
        rows={2}
        value={note}
      />
      {confirmingReject ? (
        <div className="reject-confirmation" role="alert">
          <p>Rejecting closes this workflow without creating a purchase order.</p>
          <div className="review-actions">
            <button
              className="button button--danger"
              disabled={busy}
              onClick={() => onReview("reject", note)}
              type="button"
            >
              {busy ? "Applying decision…" : "Confirm rejection"}
            </button>
            <button
              className="button button--quiet"
              disabled={busy}
              onClick={() => setConfirmingReject(false)}
              type="button"
            >
              Keep review open
            </button>
          </div>
        </div>
      ) : (
        <div className="review-actions">
          <button
            className="button button--primary"
            disabled={busy}
            onClick={() => onReview("approve", note)}
            type="button"
          >
            {busy ? "Applying decision…" : "Approve and create PO"}
          </button>
          <button
            className="button button--danger"
            disabled={busy}
            onClick={() => setConfirmingReject(true)}
            type="button"
          >
            Reject purchase
          </button>
        </div>
      )}
    </section>
  );
}
