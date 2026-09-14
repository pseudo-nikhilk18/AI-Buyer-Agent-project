import { useEffect, useState } from "react";

import { getCase, getCases, reviewRun, runCase } from "./api";
import { CaseQueue } from "./components/CaseQueue";
import { EvidenceLedger } from "./components/EvidenceLedger";
import { InventoryProjection } from "./components/InventoryProjection";
import { InvestigationRecord } from "./components/InvestigationRecord";
import { PolicyChecks } from "./components/PolicyChecks";
import { RunOutcome } from "./components/RunOutcome";
import { Status } from "./components/Status";
import { SystemOverview } from "./components/SystemOverview";
import { WorkflowTimeline } from "./components/WorkflowTimeline";
import { formatLabel } from "./lib/format";
import { getScenarioPresentation } from "./lib/scenarios";

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
  const scenario = detail ? getScenarioPresentation(detail) : null;
  const isAwaitingReview = run?.status === "awaiting_review";

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <a className="skip-link" href="#main-content">
        Skip to buyer-agent decision
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
        {busy ? "Updating the selected demo scenario…" : error}
      </p>

      {pageState === "loading" && cases.length === 0 ? (
        <main className="workspace-state" id="main-content" aria-live="polite">
          <span className="loading-rule" aria-hidden="true" />
          <h1>Loading Demo Scenarios…</h1>
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
          <h1>No Demo Scenarios Are Available</h1>
          <p>Seed the backend data, then reload this workspace.</p>
        </main>
      ) : null}

      {cases.length > 0 ? (
        <main id="main-content">
          <SystemOverview />
          <div className="workspace">
            <CaseQueue busy={busy} cases={cases} onSelect={handleSelect} selectedId={selectedId} />

            <div className="decision-sheet" aria-busy={pageState === "loading" || busy}>
              {detail ? (
                <>
                  <section className="case-heading">
                    <div className="case-heading__title">
                      <p className="case-heading__label">Selected Demo Scenario</p>
                      <h2>{scenario.label}</h2>
                      <p className="case-heading__context">
                        {detail.product_name} · {detail.node_name}
                      </p>
                      <p className="case-heading__id">
                        Demo ID {detail.code} · SKU {detail.sku}
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
                          ? "Buyer Agent Running…"
                          : isAwaitingReview
                            ? "Buyer Decision Required"
                            : run
                              ? "Run Again with Current Evidence"
                              : "Run Buyer Agent"}
                      </button>
                    </div>
                    <dl className="scenario-brief">
                      <div>
                        <dt>What Changed</dt>
                        <dd>{scenario.changed}</dd>
                      </div>
                      <div>
                        <dt>What the Agent Must Protect</dt>
                        <dd>{scenario.protects}</dd>
                      </div>
                    </dl>
                  </section>

                  {error ? (
                    <div className="error-banner" role="alert">
                      {error}
                    </div>
                  ) : null}

                  <RunOutcome busy={busy} detail={detail} onReview={handleReview} run={run} />
                  <InvestigationRecord run={run} />

                  <section className="supporting-proof" aria-labelledby="supporting-proof-heading">
                    <div className="supporting-proof__heading">
                      <h2 id="supporting-proof-heading">Supporting Evidence</h2>
                      <p>
                        Open these records to inspect how the agent reached and verified its
                        decision.
                      </p>
                    </div>
                    <details>
                      <summary>
                        <span>Evidence and Inventory Projection</span>
                        <small>Source freshness, demand, supply, and stock path</small>
                      </summary>
                      <div className="supporting-proof__content">
                        <EvidenceLedger detail={detail} run={run} />
                        <InventoryProjection candidate={run?.selected_candidate} />
                      </div>
                    </details>
                    <details>
                      <summary>
                        <span>Safety Policy Checks</span>
                        <small>Hard constraints and authorization boundaries</small>
                      </summary>
                      <div className="supporting-proof__content">
                        <PolicyChecks checks={run?.analysis?.policy_checks} />
                      </div>
                    </details>
                    <details>
                      <summary>
                        <span>Technical Workflow Trace</span>
                        <small>The nodes completed during this agent run</small>
                      </summary>
                      <div className="supporting-proof__content">
                        <WorkflowTimeline run={run} />
                      </div>
                    </details>
                  </section>
                </>
              ) : error ? (
                <div className="sheet-error" role="alert">
                  <h2>This Purchasing Scenario Could Not Load</h2>
                  <p>{error}</p>
                  <button
                    className="button button--primary"
                    onClick={() => handleSelect(selectedId, true)}
                    type="button"
                  >
                    Try This Scenario Again
                  </button>
                </div>
              ) : (
                <div className="sheet-loading" aria-live="polite">
                  <span className="loading-rule" aria-hidden="true" />
                  Loading Scenario Evidence…
                </div>
              )}
            </div>
          </div>
        </main>
      ) : null}
    </div>
  );
}

export default App;
