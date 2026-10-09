import type { Claim, RegistrySnapshot, ScenariosResponse } from "./types";

// Base URL for the FastAPI backend. Configurable via NEXT_PUBLIC_API_URL so
// it can point somewhere other than localhost in other environments; falls
// back to the documented default for local dev.
export function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

// Turns an http(s) API base URL into the matching ws(s) URL for a claim's
// stream socket.
export function getClaimWsUrl(threadId: string): string {
  const base = getApiUrl();
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}/api/claims/${threadId}/stream`;
}

export async function fetchScenarios(): Promise<ScenariosResponse> {
  const res = await fetch(`${getApiUrl()}/api/scenarios`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET /api/scenarios failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchScenario(id: string): Promise<ScenariosResponse["scenarios"][number] | null> {
  const { scenarios } = await fetchScenarios();
  return scenarios.find((s) => s.id === id) ?? null;
}

export type ClaimFields = Omit<Claim, "claim_id">;

export async function submitClaim(claim: ClaimFields): Promise<{ thread_id: string; claim_id: string }> {
  const res = await fetch(`${getApiUrl()}/api/claims`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(claim),
  });
  if (!res.ok) {
    throw new Error(`POST /api/claims failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchRegistry(): Promise<RegistrySnapshot> {
  const res = await fetch(`${getApiUrl()}/api/registry`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET /api/registry failed: ${res.status}`);
  }
  return res.json();
}

export async function askChat(question: string, sku?: string): Promise<{ answer: string }> {
  const res = await fetch(`${getApiUrl()}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, sku }),
  });
  if (!res.ok) {
    throw new Error(`POST /api/chat failed: ${res.status}`);
  }
  return res.json();
}
