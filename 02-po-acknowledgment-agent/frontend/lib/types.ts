// Types mirroring the FastAPI backend's response/message shapes exactly.
// See backend/main.py for the source of truth.

export type Scenario = {
  id: string;
  po_number: string;
  supplier: string;
  ordered_qty: number;
  ordered_date: string;
  hours_since_po: number;
  summary: string;
  image: string | null;
};

export type Risk = "low" | "medium" | "high";

export type Action = "log_only" | "send_chase" | "escalate_unclear" | "escalate_mismatch";

export type TriggerData = {
  po_number: string;
  supplier: string;
  reason: "supplier_reply_received" | "48h_elapsed_no_acknowledgment" | "nothing_to_do_yet";
  matched_via: "same_thread" | "reference_number_match_across_threads" | null;
  hours_since_po: number;
};

export type PerceiveData = {
  situation: "pending" | "no_acknowledgment" | "unclear" | "confirmed_as_ordered" | "confirmed_with_change";
  confidence: number;
  extracted_qty: number | null;
  extracted_date: string | null;
  attachment_confidence: number | null;
  notes: string;
  source: "none" | "text" | "attachment";
};

export type DecideData = {
  action: Action;
  requires_escalation: boolean;
  hard_invariant_triggered: boolean;
  risk: Risk;
  approved: boolean | null;
  approved_by: string | null;
  rationale: string;
};

// The two interrupt kinds this graph produces — human_approval always
// carries "action_approval", escalate always carries "escalation". Which
// one arrived tells the frontend how to label and render the pending card.
export type ActionApprovalInterrupt = {
  kind: "action_approval";
  po_number: string;
  supplier: string;
  proposed_action: Action;
  rationale: string;
};

export type EscalationInterrupt = {
  kind: "escalation";
  po_number: string;
  supplier: string;
  action: Action;
  rationale: string;
  perceived_situation: PerceiveData["situation"];
  confidence: number;
  extracted_qty: number | null;
  extracted_date: string | null;
  ordered_qty: number;
  ordered_date: string;
  hard_invariant_triggered: boolean;
};

export type InterruptData = ActionApprovalInterrupt | EscalationInterrupt;

export type ActData = {
  outcome: string;
  approved: boolean;
  approved_by: string | null;
};

export type LogEntry = {
  timestamp: string;
  po_number: string;
  supplier: string;
  trigger: TriggerData;
  perception: PerceiveData;
  decision: DecideData;
  action_result: { outcome: string } | null;
  escalation_result: { acknowledged_by: string | null; note: string | null } | null;
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
  | { type: "trigger"; data: TriggerData }
  | { type: "perceive"; data: PerceiveData }
  | { type: "decide"; data: DecideData }
  | { type: "interrupt"; data: InterruptData }
  | { type: "act"; data: ActData }
  | { type: "log"; data: LogEntry }
  | { type: "done"; data: DoneData }
  | { type: "error"; data: ErrorData };

// The only messages the client ever sends, and only in reply to an
// "interrupt" — shape depends on which kind of interrupt arrived.
export type ResumeMessage =
  | { type: "resume"; kind: "action_approval"; approved: boolean; approved_by: string | null }
  | { type: "resume"; kind: "escalation"; acknowledged_by: string | null; note: string | null };

// A single row rendered in the live timeline. Built client-side from
// incoming trigger/perceive/decide/act/log messages, plus a resolved
// marker for whichever interrupt kind just got answered, so each row
// carries everything it needs to render without looking at neighbors.
export type TimelineRow =
  | { kind: "trigger"; id: string; data: TriggerData }
  | { kind: "perceive"; id: string; data: PerceiveData }
  | { kind: "decide"; id: string; data: DecideData }
  | { kind: "act"; id: string; data: ActData }
  | { kind: "log"; id: string; data: LogEntry }
  | { kind: "interrupt-resolved"; id: string; data: InterruptData };
