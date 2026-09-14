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
  const evidenceByTool = new Map((run?.evidence ?? []).map((record) => [record.tool_name, record]));
  const unavailableTools = new Set(run?.evidence_assessment?.missing_tools ?? []);

  if (!attempts.length) {
    return <p className="empty-copy">The evidence plan appears after the agent runs.</p>;
  }

  return (
    <div className="investigation-attempts">
      {attempts.map((attempt) => (
        <div className="investigation-attempt" key={attempt.attempt}>
          <div className="investigation-attempt__summary">
            <span>Investigation pass {attempt.attempt}</span>
            <p>{attempt.plan.summary}</p>
            {attempt.missing_sources_before?.length ? (
              <small>
                Retried missing source: {attempt.missing_sources_before.map(formatLabel).join(", ")}
              </small>
            ) : null}
          </div>
          <ol className="source-list">
            {attempt.plan.tool_requests.map((request) => (
              <li key={request.tool_name}>
                <div className="source-list__heading">
                  <strong>{formatLabel(request.tool_name)}</strong>
                  {evidenceByTool.has(request.tool_name) ? (
                    <span>
                      {evidenceByTool.get(request.tool_name)?.is_fresh
                        ? "SQL data retrieved"
                        : "SQL data retrieved · stale"}
                    </span>
                  ) : unavailableTools.has(request.tool_name) ? (
                    <span className="source-list__unavailable">
                      SQL query ran · data unavailable
                    </span>
                  ) : (
                    <span>Not retrieved</span>
                  )}
                </div>
                <p>{request.purpose}</p>
                <small>{request.questions.join(" · ")}</small>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
