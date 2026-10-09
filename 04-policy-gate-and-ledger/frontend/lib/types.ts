// Types mirroring the FastAPI backend's response/message shapes exactly.
// See backend/main.py for the source of truth.

export type RequestType = "operational" | "governance" | "reversal_check";

// -- scenarios --------------------------------------------------------

export type ReasoningStep = {
  factor: string;
  weight: number;
  value: unknown;
  note: string;
};

export type ActionPayload = {
  description: string;
  inputs: Record<string, unknown>;
  model_version: string;
  reasoning_path: ReasoningStep[];
};

export type BoundaryPayload = {
  max_competing_orders?: number | null;
  max_exposure_inr?: number | null;
  notes?: string;
};

export type ReversalTriggerPayload = {
  name: string;
  metric: string;
  comparison: string;
  threshold: number;
  window_label: string;
} | null;

export type OperationalRequestPayload = {
  agent_id: string;
  action: ActionPayload;
};

export type GovernanceProposalPayload = {
  agent_id: string;
  proposer: string;
  approver: string;
  from_tier: number;
  to_tier: number;
  new_boundary: BoundaryPayload;
  track_record_count: number | null;
  track_record_minimum: number | null;
  track_record_label: string;
  reversal_trigger: ReversalTriggerPayload;
  re_review_date: string | null;
  rationale: string;
  today: string;
};

export type ReversalCheckPayload = {
  agent_id: string;
  recent_decisions: { missed_commitment: boolean; escalated: boolean }[];
};

export type Scenario =
  | { id: string; request_type: "operational"; title: string; description: string; payload: OperationalRequestPayload }
  | { id: string; request_type: "governance"; title: string; description: string; payload: GovernanceProposalPayload }
  | { id: string; request_type: "reversal_check"; title: string; description: string; payload: ReversalCheckPayload };

// -- agent registry -----------------------------------------------------

export type Agent = {
  agent_id: string;
  display_name: string;
  tier: number;
  tier_label: string;
  boundary_description: string;
  escalation_contact: string;
  policy_version: string;
  reversal_trigger_description: string | null;
  re_review_date: string | null;
  track_record_count: number;
  track_record_label: string;
};

// -- run creation ---------------------------------------------------------

export type CreateRunResponse = { thread_id: string };

// -- websocket message payloads (one per node that can fire) -------------

export type BoundaryCheck = {
  within_boundary: boolean;
  reason: string;
  tier: number;
  policy_version: string;
  boundary_description: string;
};

export type OperationalDecision = {
  acted: boolean;
  acted_by: string | null;
  approved_by: string | null;
  escalated: boolean;
  notes: string;
};

export type Validation = {
  approved: boolean;
  failed_conditions: string[];
  checked_conditions: string[];
};

export type Approval = {
  approved: boolean;
  approved_by: string | null;
  notes: string;
};

export type AppliedState = {
  new_tier: number;
  new_policy_version: string;
  new_boundary: string;
};

export type ReversalResult = {
  fired: boolean;
  observed_value: number | null;
  explanation: string;
};

export type EscalationInterruptData = {
  agent_id: string;
  action: ActionPayload;
  boundary_check: BoundaryCheck;
  escalation_contact: string;
};

export type SignoffInterruptData = {
  proposal: Record<string, unknown>;
  validation: Validation;
  approver: string;
  proposer: string;
};

export type InterruptData = EscalationInterruptData | SignoffInterruptData;

// Final graph state values, as sent in the "done" message. Every field
// is optional because which ones are populated depends on which of the
// three flows (and which branch within it) actually ran.
export type DoneData = {
  request_type: RequestType;
  decision_id: string | null;
  boundary_check?: BoundaryCheck | null;
  operational_decision?: OperationalDecision | null;
  validation?: Validation | null;
  approval?: Approval | null;
  applied_state?: AppliedState | null;
  reversal_result?: ReversalResult | null;
  [key: string]: unknown;
};

export type ErrorData = { message: string };

// Discriminated union of every message the server can send on the run
// WebSocket, one JSON object per message. `node` message carries the
// raw state update returned by whichever LangGraph node just fired —
// field names are exactly policy_gate_graph.py's own node return values.
export type ServerMessage =
  | { type: "node"; node: string; data: Record<string, unknown> }
  | { type: "interrupt"; node: "escalate_operational" | "approver_signoff"; data: InterruptData }
  | { type: "done"; data: DoneData }
  | { type: "error"; data: ErrorData };

// The only message the client ever sends, and only in reply to an
// "interrupt" message.
export type ResumeMessage = {
  type: "resume";
  approved: boolean;
  approved_by: string | null;
  notes?: string;
};

// A single row rendered in the live timeline. Built client-side from
// incoming node/interrupt-resolution messages so each row carries
// everything it needs to render without looking at neighbors.
export type TimelineRow =
  | { kind: "node"; id: string; node: string; data: Record<string, unknown> }
  | {
      kind: "interrupt-resolved";
      id: string;
      node: "escalate_operational" | "approver_signoff";
      data: InterruptData;
      approved: boolean;
      approvedBy: string | null;
      notes: string;
    };

// -- decision ledger -------------------------------------------------------

export type HumanAction = {
  who: string;
  when: string;
  action: string;
  notes?: string;
};

export type DecisionRecord = {
  decision_id: string;
  agent_id: string;
  tier: number;
  timestamp: string;
  record_type: "operational" | "governance";
  inputs: Record<string, unknown>;
  policy_version: string;
  model_version: string;
  reasoning_path: ReasoningStep[];
  human_actions: HumanAction[];
  outcome: Record<string, unknown> | null;
  amends: string | null;
  prev_hash: string;
  record_hash: string;
};

export type LedgerListResponse = {
  records: DecisionRecord[];
  total_records: number;
  chain_intact: boolean;
  chain_broken_at: string | null;
};

export type ReconstructedDecision = {
  decision_id: string;
  agent_id: string;
  tier: number;
  timestamp: string;
  record_type: "operational" | "governance";
  inputs: Record<string, unknown>;
  policy_version: string;
  model_version: string;
  reasoning_path: ReasoningStep[];
  human_actions: HumanAction[];
  outcome: Record<string, unknown> | null;
  amendment_count: number;
};
