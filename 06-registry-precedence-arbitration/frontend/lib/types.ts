// Types mirroring the FastAPI backend's response/message shapes exactly.
// See backend/main.py for the source of truth.

export type Claim = {
  claim_id?: string;
  plant: string;
  supplier: string;
  lot_id: string;
  sku: string;
  quantity_needed: number;
  commitment_tier: number | null;
  days_of_cover: number | null;
  requested_at: number;
  requested_at_display: string;
};

export type ScenarioClaim = Claim & { key: string; label: string };

export type ExpectedOutcome = "granted" | "arbitrated" | "escalated";

export type Scenario = {
  id: string;
  title: string;
  summary: string;
  expected_outcome: ExpectedOutcome;
  claim_count: number;
  claims: ScenarioClaim[];
};

export type ScenariosResponse = {
  supplier: string;
  bolt_sku: string;
  image: string | null;
  scenarios: Scenario[];
};

export type Outcome = {
  claim_id: string;
  plant: string;
  result: "granted" | "granted_after_arbitration";
  reason: string;
};

export type SubmitClaimEntry = {
  event: "submit_claim";
  plant: string;
  lot_id: string;
  claim: Claim;
};

export type CheckRegistryData = { collisions: Claim[] };

export type AlternateSuggestion = {
  type: "alternate_lot" | "alternate_supplier" | "expedite";
  supplier: string;
  lot_id: string;
  available_qty: number;
  lead_time_days: number;
  note: string;
  for_plant: string;
  original_lot_id: string;
  sku: string;
  message: string;
};

export type ArbitrationData = {
  needs_escalation: boolean;
  escalation_reason?: string;
  computation: string[];
  competing_claims: Claim[];
  winner_claim?: Claim;
  losers?: Claim[];
  alternate_suggestions?: AlternateSuggestion[];
  resolved_by_human?: string;
  human_note?: string;
};

// escalate_to_kavitas_team's interrupt() payload.
export type InterruptData = {
  reason: string;
  competing_claims: Claim[];
  escalated_to: string;
};

export type LogEntry = {
  timestamp: string;
  claim_id: string;
  plant: string;
  supplier: string;
  lot_id: string;
  outcome: Outcome;
  type: "clear" | "arbitrated";
  competing_claims?: Claim[];
  computation?: string[];
  winner?: string;
  escalated_to_human?: boolean;
  alternate_suggestions?: AlternateSuggestion[];
};

// Discriminated union of every message the server can send on a claim's
// run WebSocket, one JSON object per message. Node names match
// coordination_graph.py's node names exactly.
export type ServerMessage =
  | { type: "submit_claim"; data: SubmitClaimEntry }
  | { type: "check_registry"; data: CheckRegistryData }
  | { type: "grant"; data: Outcome }
  | { type: "arbitrate"; data: ArbitrationData }
  | { type: "interrupt"; data: InterruptData }
  | { type: "escalate_to_kavitas_team"; data: ArbitrationData }
  | { type: "grant_winner"; data: Outcome }
  | { type: "suggest_alternate_for_loser"; data: { alternate_suggestions: AlternateSuggestion[] } }
  | { type: "log"; data: LogEntry }
  | { type: "done"; data: { log: LogEntry[] } }
  | { type: "error"; data: { message: string } };

// The only message the client ever sends, and only in reply to an
// "interrupt" — escalate_to_kavitas_team's interrupt() expects exactly
// this shape (see coordination_graph.py).
export type ResumeMessage = {
  type: "resume";
  winner_plant: string;
  decided_by?: string;
  note?: string;
};

// A single row rendered in one claim's live timeline. Built client-side
// from incoming messages so each row carries everything it needs to
// render without looking at neighbors.
export type TimelineRow =
  | { kind: "submit_claim"; id: string; data: SubmitClaimEntry }
  | { kind: "check_registry"; id: string; data: CheckRegistryData }
  | { kind: "grant"; id: string; data: Outcome }
  | { kind: "arbitrate"; id: string; data: ArbitrationData }
  | { kind: "grant_winner"; id: string; data: Outcome }
  | { kind: "suggest_alternate_for_loser"; id: string; data: { alternate_suggestions: AlternateSuggestion[] } }
  | { kind: "escalation-resolved"; id: string; data: InterruptData; decision: ResumeMessage }
  | { kind: "log"; id: string; data: LogEntry };

export type RegistryHoldStatus = "pending" | "confirmed" | "closed_lost";

export type RegistryHold = { plant: string; status: RegistryHoldStatus };

export type RegistrySnapshot = {
  holds: Record<string, RegistryHold[]>;
  audit_log: LogEntry[];
};
