import { useEffect, useState } from "react";

import { getCase, getCases, reviewRun, runCase } from "./api";
import { EvidenceLedger } from "./components/EvidenceLedger";
import { InventoryProjection } from "./components/InventoryProjection";
import { PolicyChecks } from "./components/PolicyChecks";
import { RunOutcome } from "./components/RunOutcome";
import { Status } from "./components/Status";
import { TestSuite } from "./components/TestSuite";
import { WorkflowTimeline } from "./components/WorkflowTimeline";
import { formatLabel } from "./lib/format";

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
  const [busyCaseId, setBusyCaseId] = useState(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadTests() {
      try {
        const caseList = await getCases(controller.signal);
        const requestedId = new URLSearchParams(window.location.search).get("case");
        const requested = caseList.find((item) => item.id === requestedId);
        const requestedDetail = requested ? await getCase(requested.id, controller.signal) : null;
        setCases(caseList);
        setSelectedId(requested?.id ?? null);
        setDetail(requestedDetail);
        if (!requested) syncCaseUrl(null);
        setPageState("ready");
      } catch (loadError) {
        if (loadError.name === "AbortError") return;
        setError(loadError.message);
        setPageState("error");
      }
    }

    loadTests();
    return () => controller.abort();
  }, []);

  async function refreshCase(caseId) {
    const [nextCases, nextDetail] = await Promise.all([getCases(), getCase(caseId)]);
    setCases(nextCases);
    setDetail(nextDetail);
  }

  async function handleView(caseId) {
    if (busyCaseId) return;
    setBusyCaseId(caseId);
    setSelectedId(caseId);
    setDetail(null);
    setError("");
    syncCaseUrl(caseId);
    try {
      setDetail(await getCase(caseId));
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setBusyCaseId(null);
    }
  }

  async function handleRun(item) {
    if (busyCaseId) return;
    setBusyCaseId(item.id);
    setSelectedId(item.id);
    setDetail(null);
    setError("");
    syncCaseUrl(item.id);
    try {
      await runCase(item.id);
      await refreshCase(item.id);
    } catch (runError) {
      setError(runError.message);
      try {
        setDetail(await getCase(item.id));
      } catch {
        setDetail(null);
      }
    } finally {
      setBusyCaseId(null);
    }
  }

  async function handleReview(decision, note) {
    const run = detail?.latest_run;
    if (!run) return;
    setReviewBusy(true);
    setError("");
    try {
      await reviewRun(run.id, decision, note);
      await refreshCase(detail.id);
    } catch (reviewError) {
      setError(reviewError.message);
    } finally {
      setReviewBusy(false);
    }
  }

  const run = detail?.latest_run;

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">
        Skip to agent tests
      </a>
      <header className="app-header">
        <div className="app-header__inner">
          <a className="brand" href="/">
            Buyer Agent
          </a>
          <span>AI purchasing decisions with verified actions</span>
          {run?.mode ? <span className="mode-mark">{formatLabel(run.mode)} run</span> : null}
        </div>
      </header>

      <p className="sr-only" aria-live="polite">
        {busyCaseId ? "The purchasing agent is running a test." : error}
      </p>

      <main className="evaluation-shell" id="main-content">
        {pageState === "loading" ? (
          <section className="page-state" aria-live="polite">
            <span className="loading-rule" aria-hidden="true" />
            <h1>Loading agent tests…</h1>
            <p>Connecting to the API and PostgreSQL dataset.</p>
          </section>
        ) : null}

        {pageState === "error" ? (
          <section className="page-state" role="alert">
            <h1>Agent tests could not load</h1>
            <p>{error}</p>
            <button
              className="button button--primary"
              onClick={() => location.reload()}
              type="button"
            >
              Try again
            </button>
          </section>
        ) : null}

        {pageState === "ready" && cases.length === 0 ? (
          <section className="page-state">
            <h1>No tests are available</h1>
            <p>Run the backend seed command, then reload this page.</p>
          </section>
        ) : null}

        {pageState === "ready" && cases.length > 0 ? (
          <>
            <TestSuite
              busyCaseId={busyCaseId}
              cases={cases}
              onRun={handleRun}
              onView={handleView}
              selectedId={selectedId}
            />

            {error ? (
              <div className="error-banner" role="alert">
                {error}
              </div>
            ) : null}

            {busyCaseId && !detail ? (
              <section className="running-panel" aria-live="polite">
                <span className="loading-rule" aria-hidden="true" />
                <div>
                  <h2>Agent is investigating the purchasing situation</h2>
                  <p>
                    It is selecting evidence, comparing quantities, and checking whether an action
                    is safe.
                  </p>
                </div>
              </section>
            ) : null}

            {detail ? (
              <article className="test-result" aria-labelledby="test-result-heading">
                <header className="test-result__header">
                  <div>
                    <p className="eyebrow">Test result · {detail.code}</p>
                    <h1 id="test-result-heading">{detail.title}</h1>
                    <p>{detail.test_purpose}</p>
                  </div>
                  <div className="test-result__actions">
                    <Status value={run?.status ?? detail.status} />
                    {run ? (
                      <span className="run-engine">
                        {run.mode === "live"
                          ? `Live AI · ${formatLabel(run.provider)} · ${run.model}`
                          : "Engineering replay · no AI model"}
                      </span>
                    ) : null}
                    <button
                      className="button button--quiet"
                      disabled={Boolean(busyCaseId) || reviewBusy}
                      onClick={() => handleRun(detail)}
                      type="button"
                    >
                      Run this test again
                    </button>
                  </div>
                </header>

                <RunOutcome busy={reviewBusy} detail={detail} onReview={handleReview} run={run} />

                <details className="technical-details">
                  <summary>
                    <span>Technical details</span>
                    <small>
                      Evidence records, purchasing rules, inventory projection, and graph trace
                    </small>
                  </summary>
                  <div className="technical-details__content">
                    <EvidenceLedger detail={detail} run={run} />
                    <PolicyChecks checks={run?.analysis?.policy_checks} />
                    <InventoryProjection candidate={run?.selected_candidate} />
                    <WorkflowTimeline run={run} />
                  </div>
                </details>
              </article>
            ) : null}
          </>
        ) : null}
      </main>
    </div>
  );
}

export default App;
