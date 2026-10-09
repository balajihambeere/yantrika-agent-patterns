// Types mirroring the FastAPI backend's response/message shapes exactly.
// See backend/main.py for the source of truth.

export type Product = {
  sku: string;
  name: string;
  image: string;
  opening_balance: number;
  run_rate_per_minute: number;
  event_count: number;
};

export type Risk = "low" | "medium" | "high";

export type Action =
  | "no_action"
  | "alert_floor_and_stores"
  | "expedite_replacement_shipment";

export type ObserveData = {
  minutes_after_start: number;
  balance: number;
  last_transaction: string;
};

export type DecideData = {
  action: Action;
  rationale: string;
  risk: Risk;
  requires_human: boolean;
  approved: boolean;
  approved_by: string | null;
};

export type InterruptData = {
  action: Action;
  rationale: string;
  risk: Risk;
};

export type ActData = {
  outcome: string;
};

export type LogEntry = {
  timestamp: string;
  observation: ObserveData;
  decision: DecideData;
  outcome: string;
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
  | { type: "observe"; data: ObserveData }
  | { type: "decide"; data: DecideData }
  | { type: "interrupt"; data: InterruptData }
  | { type: "act"; data: ActData }
  | { type: "done"; data: DoneData }
  | { type: "error"; data: ErrorData };

// The only message the client ever sends, and only in reply to an
// "interrupt" message.
export type ResumeMessage = {
  type: "resume";
  approved: boolean;
  approved_by: string | null;
};

// A single row rendered in the live timeline. Built client-side from
// incoming observe/decide/act/interrupt-resolution messages so each row
// carries everything it needs to render without looking at neighbors.
export type TimelineRow =
  | { kind: "observe"; id: string; data: ObserveData }
  | { kind: "decide"; id: string; data: DecideData }
  | { kind: "act"; id: string; data: ActData }
  | { kind: "interrupt-resolved"; id: string; data: InterruptData; approved: boolean; approvedBy: string | null };
