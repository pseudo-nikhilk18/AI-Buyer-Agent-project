import { useEffect, useState } from "react";

import { getCase, getCases, reviewRun, runCase } from "./api";
import { CaseQueue } from "./components/CaseQueue";
import { EvidenceLedger } from "./components/EvidenceLedger";
import { InventoryProjection } from "./components/InventoryProjection";
import { PolicyChecks } from "./components/PolicyChecks";
import { ReviewPanel } from "./components/ReviewPanel";
import { Status } from "./components/Status";
import { WorkflowTimeline } from "./components/WorkflowTimeline";
import { formatCurrency, formatDate, formatLabel, formatQuantity } from "./lib/format";

function decisionQuantity(run) {
  if (!run) return null;
  if (run.decision?.decision === "reject") return 0;
  return run.selected_candidate?.quantity ?? run.proposed_quantity;
}

function syncCaseUrl(caseId) {
  const url = new URL(window.location.href);
  if (caseId) url.searchParams.set("case", caseId);
  else url.searchParams.delete("case");
  window.history.replaceState(null, "", url);
}

function App() {
  const [cases, setCases] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [pageState, setPageState] = useState("loading");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadWorkspace() {
      try {
        const caseList = await getCases(controller.signal);
        const requestedCaseId = new URLSearchParams(window.location.search).get("case");
        const firstCase = caseList.find((item) => item.id === requestedCaseId) ?? caseList[0];
        const firstDetail = firstCase ? await getCase(firstCase.id, controller.signal) : null;
        setCases(caseList);
        setSelectedId(firstCase?.id ?? null);
        setDetail(firstDetail);
        setPageState("ready");
        syncCaseUrl(firstCase?.id);
      } catch (loadError) {
        if (loadError.name === "AbortError") return;
        setError(loadError.message);
        setPageState("error");
      }
    }

    loadWorkspace();
    return () => controller.abort();
  }, []);

  async function handleSelect(caseId, force = false) {
    if ((!force && caseId === selectedId) || busy) return;

    setBusy(true);
    setSelectedId(caseId);
    syncCaseUrl(caseId);
    setDetail(null);
    setError("");
    setPageState("loading");
    try {
      const nextDetail = await getCase(caseId);
      setDetail(nextDetail);
      setPageState("ready");
    } catch (loadError) {
      setError(loadError.message);
      setPageState("error");
    } finally {
      setBusy(false);
    }
  }

  async function refreshCase(caseId) {
    const [nextCases, nextDetail] = await Promise.all([getCases(), getCase(caseId)]);
    setCases(nextCases);
    setDetail(nextDetail);
  }

  async function handleRun() {
    if (!detail) return;

    setBusy(true);
    setError("");
    try {
      await runCase(detail.id);
      await refreshCase(detail.id);
    } catch (runError) {
      setError(runError.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleReview(decision, note) {
    const run = detail?.latest_run;
    if (!run) return;

    setBusy(true);
    setError("");
    try {
      await reviewRun(run.id, decision, note);
      await refreshCase(detail.id);
    } catch (reviewError) {
      setError(reviewError.message);
    } finally {
      setBusy(false);
    }
  }

  const run = detail?.latest_run;
  const selectedQuantity = decisionQuantity(run);
  const quantityDifference =
    selectedQuantity === null || !detail ? null : selectedQuantity - detail.recommended_quantity;
  const isAwaitingReview = run?.status === "awaiting_review";

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <a className="skip-link" href="#main-content">
        Skip to case decision
      </a>
      <header className="app-header">
        <div className="app-header__inner">
          <a className="brand" href="/">
            Buyer Agent
          </a>
          <p>Purchasing decision control</p>
          {run?.mode ? <span className="mode-mark">{formatLabel(run.mode)} mode</span> : null}
        </div>
      </header>
      <p className="sr-only" aria-live="polite">
        {busy ? "Updating purchasing case…" : error}
      </p>

      {pageState === "loading" && cases.length === 0 ? (
        <main className="workspace-state" id="main-content" aria-live="polite">
          <span className="loading-rule" aria-hidden="true" />
          <h1>Loading Purchasing Cases…</h1>
          <p>Connecting to the decision API and current evidence.</p>
        </main>
      ) : null}

      {pageState === "error" && cases.length === 0 ? (
        <main className="workspace-state" id="main-content" role="alert">
          <h1>The Buyer Workspace Could Not Load</h1>
          <p>{error}</p>
          <button
            className="button button--primary"
            onClick={() => window.location.reload()}
            type="button"
          >
            Try Again
          </button>
        </main>
      ) : null}

      {pageState === "ready" && cases.length === 0 ? (
        <main className="workspace-state" id="main-content">
          <h1>No Purchasing Cases Are Available</h1>
          <p>Seed the backend data, then reload this workspace.</p>
        </main>
      ) : null}

      {cases.length > 0 ? (
        <main className="workspace" id="main-content">
          <CaseQueue busy={busy} cases={cases} onSelect={handleSelect} selectedId={selectedId} />

          <div className="decision-sheet" aria-busy={pageState === "loading" || busy}>
            {detail ? (
              <>
                <section className="case-heading">
                  <div>
                    <p className="case-heading__code">{detail.code}</p>
                    <h1>{detail.title}</h1>
                    <p className="case-heading__context">
                      {detail.product_name} · {detail.sku} · {detail.node_name}
                    </p>
                  </div>
                  <div className="case-heading__action">
                    <Status value={run?.status ?? detail.status} />
                    <button
                      className="button button--primary"
                      disabled={busy || isAwaitingReview}
                      onClick={handleRun}
                      type="button"
                    >
                      {busy
                        ? "Workflow Running…"
                        : run
                          ? "Run with Current Data"
                          : "Run Investigation"}
                    </button>
                  </div>
                </section>

                {error ? (
                  <div className="error-banner" role="alert">
                    {error}
                  </div>
                ) : null}

                <section className="decision-band" aria-labelledby="decision-heading">
                  <div className="decision-band__copy">
                    <h2 id="decision-heading">Current Decision</h2>
                    <strong>
                      {run?.decision ? formatLabel(run.decision.decision) : "Not evaluated"}
                    </strong>
                    <p>
                      {run?.decision?.summary ??
                        "The recommendation has not yet been checked against current evidence and policy."}
                    </p>
                  </div>
                  <div className="quantity-comparison">
                    <div>
                      <span>Recommendation</span>
                      <strong>{formatQuantity(detail.recommended_quantity)}</strong>
                      <small>units</small>
                    </div>
                    <span className="quantity-comparison__divider" aria-hidden="true" />
                    <div>
                      <span>Selected quantity</span>
                      <strong>{formatQuantity(selectedQuantity)}</strong>
                      <small>
                        {quantityDifference === null
                          ? "pending"
                          : quantityDifference === 0
                            ? "unchanged"
                            : `${quantityDifference > 0 ? "+" : ""}${formatQuantity(quantityDifference)} units`}
                      </small>
                    </div>
                  </div>
                  <dl className="decision-meta">
                    <div>
                      <dt>Authorization</dt>
                      <dd>
                        {run?.authorization ? (
                          <Status value={run.authorization.status} />
                        ) : (
                          "Pending"
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Proposed spend</dt>
                      <dd>{formatCurrency(run?.proposed_spend_minor, detail.supplier.currency)}</dd>
                    </div>
                    <div>
                      <dt>Last evaluated</dt>
                      <dd>{run ? formatDate(run.started_at, true) : "Never"}</dd>
                    </div>
                  </dl>
                </section>

                {isAwaitingReview ? (
                  <ReviewPanel busy={busy} key={run.id} onReview={handleReview} run={run} />
                ) : null}

                <EvidenceLedger detail={detail} run={run} />
                <InventoryProjection candidate={run?.selected_candidate} />
                <PolicyChecks checks={run?.analysis?.policy_checks} />
                <WorkflowTimeline run={run} />
              </>
            ) : error ? (
              <div className="sheet-error" role="alert">
                <h1>This Purchasing Case Could Not Load</h1>
                <p>{error}</p>
                <button
                  className="button button--primary"
                  onClick={() => handleSelect(selectedId, true)}
                  type="button"
                >
                  Try This Case Again
                </button>
              </div>
            ) : (
              <div className="sheet-loading" aria-live="polite">
                <span className="loading-rule" aria-hidden="true" />
                Loading Case Evidence…
              </div>
            )}
          </div>
        </main>
      ) : null}
    </div>
  );
}

export default App;
