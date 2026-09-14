import { evidenceSummary, formatLabel } from "../lib/format";

function attemptsFor(run) {
  if (run?.investigation_history?.length) return run.investigation_history;
  if (run?.investigation_plan) {
    return [{ attempt: 1, missing_sources_before: [], plan: run.investigation_plan }];
  }
  return [];
}

function ToolExchange({ record, request, requestedByAi, unavailable }) {
  const result = record ? evidenceSummary(request.tool_name, record.payload) : null;
  const status = record
    ? record.is_fresh
      ? "Current SQL data"
      : "Stale SQL data"
    : unavailable
      ? "No data returned"
      : "Not executed";

  return (
    <li className="tool-exchange">
      <div className="tool-exchange__request">
        <span>{requestedByAi ? "AI requested" : "Replay requested"}</span>
        <div className="tool-exchange__name">
          <strong>{formatLabel(request.tool_name)}</strong>
          <code>{request.tool_name}</code>
        </div>
        <p>{request.purpose}</p>
        <small>Question: {request.questions.join(" ")}</small>
      </div>
      <div className="tool-exchange__response" data-missing={!record}>
        <div>
          <span>Tool returned</span>
          <small>{status}</small>
        </div>
        <strong>{result?.value ?? "No evidence available"}</strong>
        <p>
          {result?.detail ??
            (unavailable
              ? "The source query completed without the required record."
              : "The workflow did not call this tool.")}
        </p>
      </div>
    </li>
  );
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
              <ToolExchange
                key={request.tool_name}
                record={evidenceByTool.get(request.tool_name)}
                request={request}
                requestedByAi={run?.mode === "live"}
                unavailable={unavailableTools.has(request.tool_name)}
              />
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
