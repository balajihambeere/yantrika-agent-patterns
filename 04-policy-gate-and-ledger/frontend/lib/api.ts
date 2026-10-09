import type {
  Agent,
  CreateRunResponse,
  GovernanceProposalPayload,
  LedgerListResponse,
  OperationalRequestPayload,
  ReconstructedDecision,
  ReversalCheckPayload,
  Scenario,
} from "./types";

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

export async function fetchAgents(): Promise<Agent[]> {
  const res = await fetch(`${getApiUrl()}/api/agents`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET /api/agents failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchLedger(limit = 50): Promise<LedgerListResponse> {
  const res = await fetch(`${getApiUrl()}/api/ledger?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET /api/ledger failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchLedgerDecision(decisionId: string): Promise<ReconstructedDecision | null> {
  const res = await fetch(`${getApiUrl()}/api/ledger/${decisionId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`GET /api/ledger/${decisionId} failed: ${res.status}`);
  }
  return res.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`POST ${path} failed: ${res.status}${detail ? ` — ${detail}` : ""}`);
  }
  return res.json();
}

export function createOperationalRequest(payload: OperationalRequestPayload): Promise<CreateRunResponse> {
  return postJson("/api/operational-requests", payload);
}

export function createGovernanceProposal(payload: GovernanceProposalPayload): Promise<CreateRunResponse> {
  return postJson("/api/governance-proposals", payload);
}

export function createReversalCheck(payload: ReversalCheckPayload): Promise<CreateRunResponse> {
  return postJson("/api/reversal-checks", payload);
}

export async function askChat(question: string, context?: { agentId?: string; decisionId?: string }): Promise<{ answer: string }> {
  const res = await fetch(`${getApiUrl()}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, agent_id: context?.agentId, decision_id: context?.decisionId }),
  });
  if (!res.ok) {
    throw new Error(`POST /api/chat failed: ${res.status}`);
  }
  return res.json();
}
