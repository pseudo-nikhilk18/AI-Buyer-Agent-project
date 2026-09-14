import { formatLabel } from "../lib/format";

function attemptsFor(run) {
  if (run?.investigation_history?.length) return run.investigation_history;
  if (run?.investigation_plan) {
    return [{ attempt: 1, missing_sources_before: [], plan: run.investigation_plan }];
  }
  return [];
}

export function InvestigationRecord({ run }) {
  const attempts = attemptsFor(run);

  return (
    <section className="investigation-record" aria-labelledby="investigation-heading">
      <header className="investigation-record__heading">
        <div>
          <p>Agent Reasoning Boundary</p>
          <h2 id="investigation-heading">Evidence Investigation</h2>
        </div>
        <p>
          {run?.mode === "live"
            ? "The model chooses evidence sources and states what each source must answer."
            : "Replay uses the required evidence set to verify deterministic safety behavior."}
        </p>
      </header>

      {attempts.length ? (
        <div className="investigation-attempts">
          {attempts.map((attempt) => (
            <article className="investigation-attempt" key={attempt.attempt}>
              <div className="investigation-attempt__summary">
                <span>Planning Pass {attempt.attempt}</span>
                <strong>{attempt.plan.summary}</strong>
                {attempt.missing_sources_before?.length ? (
                  <p>Closed gaps: {attempt.missing_sources_before.map(formatLabel).join(", ")}</p>
                ) : null}
              </div>
              <ol>
                {attempt.plan.tool_requests.map((request) => (
                  <li key={request.tool_name}>
                    <strong>{formatLabel(request.tool_name)}</strong>
                    <p>{request.purpose}</p>
                    <small>{request.questions.join(" · ")}</small>
                  </li>
                ))}
              </ol>
            </article>
          ))}
        </div>
      ) : (
        <p className="investigation-empty">
          Run the buyer agent to see which evidence it chooses and why.
        </p>
      )}
    </section>
  );
}
