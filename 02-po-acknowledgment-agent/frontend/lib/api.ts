import type { Scenario } from "./types";

// Base URL for the FastAPI backend. Configurable via NEXT_PUBLIC_API_URL so
// it can point somewhere other than localhost in other environments; falls
// back to the documented default for local dev.
export function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

// Turns an http(s) API base URL into the matching ws(s) URL for the run
// stream socket.
export function getWsUrl(threadId: string): string {
  const base = getApiUrl();
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}/api/runs/${threadId}/stream`;
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await fetch(`${getApiUrl()}/api/scenarios`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET /api/scenarios failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchScenario(id: string): Promise<Scenario | null> {
  const scenarios = await fetchScenarios();
  return scenarios.find((s) => s.id === id) ?? null;
}

export async function createRun(scenarioId: string, supervised: boolean): Promise<{ thread_id: string }> {
  const res = await fetch(`${getApiUrl()}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: scenarioId, supervised }),
  });
  if (!res.ok) {
    throw new Error(`POST /api/runs failed: ${res.status}`);
  }
  return res.json();
}

export async function askChat(question: string, scenarioId?: string): Promise<{ answer: string }> {
  const res = await fetch(`${getApiUrl()}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, scenario_id: scenarioId }),
  });
  if (!res.ok) {
    throw new Error(`POST /api/chat failed: ${res.status}`);
  }
  return res.json();
}
