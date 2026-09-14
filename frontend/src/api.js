const DEFAULT_API_BASE_URL = "http://localhost:8000/api";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : `The request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return payload;
}

export function getCases(signal) {
  return request("/cases", { signal });
}

export function getCase(caseId, signal) {
  return request(`/cases/${caseId}`, { signal });
}

export function runCase(caseId) {
  return request(`/cases/${caseId}/runs`, { method: "POST" });
}

export function reviewRun(runId, decision, note) {
  return request(`/runs/${runId}/review`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      note: note.trim() || null,
    }),
  });
}
