// Types mirroring the FastAPI backend's response/message shapes exactly.
// See backend/main.py and backend/federation_graph.py for the source of
// truth.

export type SitePositionSummary = {
  site: string;
  on_hand: number;
  buffer_target: number;
};

export type Scenario = {
  id: string;
  title: string;
  description: string;
  sku_family: string;
  connection_tier: string;
  supplier: string;
  pune_position: SitePositionSummary;
  nashik_position: SitePositionSummary;
  expect_collision: boolean;
  image: string | null;
};

// One site-scoped agent's own, narrow recommendation (site_agents.py).
export type RecommendationAction =
  | "no_action"
  | "surplus_available"
  | "offer_cross_boundary_transfer"
  | "rush_order";

export type LocalRecommendation = {
  site: string;
  sku_family: string;
  action: RecommendationAction;
  quantity: number;
  rationale: string;
  touches_other_site: string | null;
};

// The full collision report, as returned by the `arbitrate` node and
// embedded in a completed log entry. Note: the `interrupt` message's
// `collision` field is a different, narrower shape — see InterruptData.
export type CollisionReport = {
  sku_family: string;
  description: string;
  pune_recommendation: LocalRecommendation;
  nashik_recommendation: LocalRecommendation;
};

export type ApproverKey = "neha" | "shalini";

// The payload LangGraph's interrupt() carries for confirm_neha /
// confirm_shalini. `approver_key` is added server-side (not part of the
// graph's own payload) purely so the frontend can distinguish the two
// steps without string-matching full names.
export type InterruptData = {
  confirmer: string;
  role: string;
  collision: string;
  proposed_action: string;
  approver_key: ApproverKey;
};

export type Confirmation = {
  confirmed: boolean;
  confirmed_by: string;
  note: string;
};

export type IndependentActionDecision = {
  type: "independent_action";
  coordinated: false;
  pune_action: LocalRecommendation;
  nashik_action: LocalRecommendation;
  note: string;
};

export type UnilateralActDecision = {
  type: "unilateral_cross_boundary_act";
  coordinated: false;
  quantity: number;
  sku_family: string;
  note: string;
};

export type CoordinatedTransferDecision = {
  type: "coordinated_transfer";
  coordinated: true;
  quantity: number;
  sku_family: string;
  from_site: string;
  to_site: string;
  rush_order_cancelled: boolean;
  confirmed_by: string[];
  note: string;
};

export type FallbackIndependentDecision = {
  type: "fallback_independent";
  coordinated: false;
  declined_by: string[];
  pune_action: LocalRecommendation;
  nashik_action: LocalRecommendation;
  note: string;
};

export type Decision =
  | IndependentActionDecision
  | UnilateralActDecision
  | CoordinatedTransferDecision
  | FallbackIndependentDecision;

export type LogEntry = {
  timestamp: string;
  connection_tier: string;
  pune_position: { site: string; sku_family: string; on_hand: number; buffer_target: number };
  nashik_position: { site: string; sku_family: string; on_hand: number; buffer_target: number };
  pune_recommendation: LocalRecommendation;
  nashik_recommendation: LocalRecommendation;
  collision: CollisionReport | null;
  neha_confirmation: Confirmation | null;
  shalini_confirmation: Confirmation | null;
  decision: Decision;
};

export type DoneData = {
  log: LogEntry[];
};

export type ErrorData = {
  message: string;
};

// Discriminated union of every message the server can send on the run
// WebSocket, one JSON object per message.
export type ServerMessage =
  | { type: "sense_pune"; data: LocalRecommendation }
  | { type: "sense_nashik"; data: LocalRecommendation }
  | { type: "arbitrate"; data: { collision: CollisionReport | null } }
  | { type: "interrupt"; data: InterruptData }
  | { type: "act"; data: Decision }
  | { type: "log"; data: LogEntry }
  | { type: "done"; data: DoneData }
  | { type: "error"; data: ErrorData };

// The only message the client ever sends, and only in reply to an
// "interrupt". `confirmed_by` is purely informational for display — the
// server always falls back to that interrupt's own named confirmer, so a
// reply can never be misattributed to the wrong approver.
export type ResumeMessage = {
  type: "resume";
  confirmed: boolean;
  confirmed_by: string;
  note: string;
};

// A single row rendered in the live run view's timeline. Built
// client-side from incoming messages so each row carries everything it
// needs to render without looking at neighbors.
export type TimelineRow =
  | { kind: "arbitrate"; id: string; collision: CollisionReport | null }
  | {
      kind: "confirmation-resolved";
      id: string;
      approverKey: ApproverKey;
      interrupt: InterruptData;
      confirmed: boolean;
      confirmedBy: string;
      note: string;
    }
  | { kind: "act"; id: string; decision: Decision };
