const DEFAULT_API_BASE_URL = "http://localhost:8000/api";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
const HEALTH_ENDPOINT = `${API_BASE_URL}/health`;

export async function getSystemHealth(signal) {
  const response = await fetch(HEALTH_ENDPOINT, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  const result = await response.json();

  if (!response.ok && response.status !== 503) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return result;
}
