// Types mirroring the FastAPI backend's response/message shapes exactly.
// See backend/main.py (and reasoning_graph.py / reasoning_factors.py one
// directory up) for the source of truth.

export type OrderSummary = {
  account: string;
  requested_units: number;
  note: string;
};

export type Scenario = {
  id: string;
  label: string;
  sku: string;
  available_units: number;
  orders: OrderSummary[];
  description: string;
};

// A full competing order, as carried inside a "sense" message's cycle data.
export type CompetingOrder = {
  account: string;
  requested_units: number;
  contract_penalty_inr: number;
  downstream_impact_inr: number;
  strategic_score: number;
  replenishment_confidence: number;
  expedite_cost_inr: number;
  note: string;
};

export type SenseData = {
  label: string;
  available_units: number;
  orders: CompetingOrder[];
};

// One account's five-factor weighing — the substantive payload of this
// example. factor_points / factor_percentiles are keyed identically:
// contract_penalty, downstream_impact, strategic_trajectory,
// replenishment_confidence, cost_to_close_gap.
export type FactorScores = {
  account: string;
  requested_units: number;
  factor_points: Record<string, number>;
  factor_percentiles: Record<string, number>;
  weighted_total: number;
  rationale: string[];
};

export type WeighData = FactorScores[];

export type AllocationResult = {
  account: string;
  requested_units: number;
  allocated_units: number;
  fraction: number;
  status: "complete" | "partial" | "held";
  message: string | null;
};

export type RecommendData = {
  sku: string;
  cycle_label: string;
  available_units: number;
  ranking: string[];
  allocation: Record<string, AllocationResult>;
  requires_human: boolean;
  clear_agreement: boolean;
  exposure_on_losing_side: number;
  reason: string;
};

export type InterruptData = {
  sku: string;
  cycle_label: string;
  reason: string;
  exposure_on_losing_side: number;
  clear_agreement: boolean;
  reasoning: FactorScores[];
  recommended_allocation: Record<string, AllocationResult>;
};

// act's "decision" payload. `allocation` is a map of AllocationResult
// objects when the system acted autonomously or a human approved its
// recommendation as-is, but becomes a plain account -> unit-count map when
// a human overrode it with a different split (see escalate() in
// reasoning_graph.py) — the frontend has to render both shapes.
export type DecisionData = {
  allocation: Record<string, AllocationResult | number>;
  decided_by: string;
  autonomous: boolean;
  overridden: boolean;
  override_reason: string | null;
};

export type LogEntryData = {
  timestamp: string;
  sku: string;
  cycle_label: string;
  available_units: number;
  reasoning: FactorScores[];
  ranking: string[];
  recommended_allocation: Record<string, AllocationResult>;
  requires_human: boolean;
  clear_agreement: boolean;
  exposure_on_losing_side: number;
  escalation_reason: string;
  decision: DecisionData;
};

export type DoneData = {
  log: LogEntryData[];
};

export type ErrorData = {
  message: string;
};

// Discriminated union of every message the server can send on the run
// WebSocket, one JSON object per message.
export type ServerMessage =
  | { type: "sense"; data: SenseData }
  | { type: "weigh"; data: WeighData }
  | { type: "recommend"; data: RecommendData }
  | { type: "interrupt"; data: InterruptData }
  | { type: "act"; data: DecisionData }
  | { type: "log"; data: LogEntryData }
  | { type: "done"; data: DoneData }
  | { type: "error"; data: ErrorData };

// The only message the client ever sends, and only in reply to an
// "interrupt". "approve" accepts the system's recommended_allocation as-is;
// "override" supplies a different allocation (plain account -> units) and
// the human's reason for diverging from it.
export type ResumeMessage =
  | { type: "resume"; decision: "approve"; decided_by: string }
  | {
      type: "resume";
      decision: "override";
      decided_by: string;
      allocation: Record<string, number>;
      reason: string;
    };

// A single row rendered in the live timeline. Built client-side from
// incoming sense/weigh/recommend/act/log/interrupt-resolution messages so
// each row carries everything it needs to render without looking at
// neighbors.
export type TimelineRow =
  | { kind: "sense"; id: string; data: SenseData }
  | { kind: "weigh"; id: string; data: WeighData }
  | { kind: "recommend"; id: string; data: RecommendData }
  | { kind: "act"; id: string; data: DecisionData }
  | { kind: "log"; id: string; data: LogEntryData }
  | {
      kind: "escalate-resolved";
      id: string;
      data: InterruptData;
      resolution: ResumeMessage;
    };
