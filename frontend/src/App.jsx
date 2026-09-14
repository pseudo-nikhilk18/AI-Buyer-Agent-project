import { useEffect, useState } from "react";

import { getSystemHealth } from "./api";

const initialServices = [
  { key: "web", name: "Web workspace", detail: "React and Vite", status: "ready" },
  { key: "api", name: "Decision API", detail: "Waiting for FastAPI", status: "checking" },
  {
    key: "database",
    name: "Purchasing database",
    detail: "Waiting for PostgreSQL",
    status: "checking",
  },
];

function formatCheckedAt(value) {
  if (!value) return "Not checked";

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function StatusMark({ status }) {
  const label = status === "ready" ? "Ready" : status === "checking" ? "Checking" : "Unavailable";

  return (
    <span className={`status-mark status-mark--${status}`}>
      <span aria-hidden="true" className="status-mark__dot" />
      {label}
    </span>
  );
}

function App() {
  const [health, setHealth] = useState(null);
  const [requestState, setRequestState] = useState("checking");

  useEffect(() => {
    const controller = new AbortController();
    getSystemHealth(controller.signal)
      .then((result) => {
        setHealth(result);
        setRequestState("ready");
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        setHealth(null);
        setRequestState("unavailable");
      });

    return () => controller.abort();
  }, []);

  const services = initialServices.map((service) => {
    if (service.key === "web") return service;

    const serviceHealth = health?.services?.[service.key];
    return {
      ...service,
      detail:
        serviceHealth?.status === "ready"
          ? `${serviceHealth.latency_ms} ms response`
          : requestState === "checking"
            ? "Running live check"
            : "Start the local service and check again",
      status: serviceHealth?.status ?? requestState,
    };
  });

  const workspaceReady = requestState === "ready" && health?.status === "ready";

  async function handleRetry() {
    setRequestState("checking");

    try {
      const result = await getSystemHealth();
      setHealth(result);
      setRequestState("ready");
    } catch {
      setHealth(null);
      setRequestState("unavailable");
    }
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-forest/20 bg-forest text-paper">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-5 py-4 sm:px-8">
          <a className="text-lg font-semibold tracking-[-0.02em]" href="/">
            Buyer Agent
          </a>
          <div className="flex items-center gap-3 text-sm text-mist">
            <span className="hidden sm:inline">Local environment</span>
            <StatusMark status={workspaceReady ? "ready" : requestState} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-16">
        <section className="grid gap-10 border-b border-rule pb-10 lg:grid-cols-[1.4fr_0.6fr] lg:items-end">
          <div>
            <p className="mb-4 text-sm font-medium text-forest">Purchasing control workspace</p>
            <h1 className="max-w-3xl text-4xl font-semibold leading-[1.02] tracking-[-0.045em] sm:text-6xl">
              {workspaceReady
                ? "The decision path is connected."
                : "The workspace needs attention."}
            </h1>
          </div>
          <div className="border-l-4 border-signal pl-5">
            <p className="text-sm text-muted">Last live check</p>
            <p className="mt-1 text-xl font-medium">{formatCheckedAt(health?.checked_at)}</p>
            <p className="mt-3 text-sm leading-6 text-muted">
              This check reaches the API and executes a query against PostgreSQL.
            </p>
          </div>
        </section>

        <section aria-labelledby="services-heading" className="py-10">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 id="services-heading" className="text-2xl font-semibold tracking-[-0.025em]">
                Service readiness
              </h2>
              <p className="mt-1 text-sm text-muted">Real process and database checks only.</p>
            </div>
            <button
              className="border border-forest bg-forest px-4 py-2.5 text-sm font-semibold text-paper outline-none transition-colors hover:bg-ink focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
              disabled={requestState === "checking"}
              onClick={handleRetry}
              type="button"
            >
              {requestState === "checking" ? "Checking…" : "Check again"}
            </button>
          </div>

          <div className="border-y border-rule" aria-live="polite">
            {services.map((service, index) => (
              <div
                className={`grid gap-3 py-5 sm:grid-cols-[1fr_1fr_auto] sm:items-center ${index === 0 ? "" : "border-t border-rule"}`}
                key={service.key}
              >
                <p className="font-semibold">{service.name}</p>
                <p className="text-sm text-muted">{service.detail}</p>
                <StatusMark status={service.status} />
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-px overflow-hidden border border-rule bg-rule md:grid-cols-2">
          <div className="bg-paper p-6 sm:p-8">
            <h2 className="text-lg font-semibold">Connection path</h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted">
              The browser calls FastAPI through the configured local URL. The API verifies
              PostgreSQL with a direct database query before reporting readiness.
            </p>
            <p className="mt-6 font-medium text-forest">Browser → API → PostgreSQL</p>
          </div>
          <div className="bg-paper p-6 sm:p-8">
            <h2 className="text-lg font-semibold">Next workflow</h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted">
              Purchase recommendation review will build on this path with evidence gathering, policy
              checks, authorization, action, and validation.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
