"use client";

import { useState } from "react";
import type { InterruptData, ResumeMessage } from "@/lib/types";
import RiskBadge from "./RiskBadge";

export default function PendingApprovalCard({
  data,
  onResolve,
}: {
  data: InterruptData;
  onResolve: (reply: ResumeMessage) => void;
}) {
  if (data.kind === "action_approval") {
    return <ActionApprovalCard data={data} onResolve={onResolve} />;
  }
  return <EscalationCard data={data} onResolve={onResolve} />;
}

// Supervised stage: EVERY proposed action (even a clean log-only) queues
// here for a human to approve or decline before it fires.
function ActionApprovalCard({
  data,
  onResolve,
}: {
  data: Extract<InterruptData, { kind: "action_approval" }>;
  onResolve: (reply: ResumeMessage) => void;
}) {
  const [approvedBy, setApprovedBy] = useState("Neha");
  const [submitting, setSubmitting] = useState(false);

  function handle(approved: boolean) {
    if (submitting) return;
    setSubmitting(true);
    onResolve({ type: "resume", kind: "action_approval", approved, approved_by: approvedBy.trim() || null });
  }

  return (
    <div
      role="alert"
      className="rounded-lg border-2 border-accent bg-accent/10 p-4 sm:p-5 shadow-sm space-y-4"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full bg-accent animate-pulse" />
          <h3 className="font-semibold text-accent uppercase tracking-wide text-base">
            Approval needed
          </h3>
        </div>
        <RiskBadge risk="low" />
      </div>

      <div className="space-y-1">
        <p className="font-mono text-base text-soft">
          {data.po_number} · {data.supplier}
        </p>
        <p className="font-mono text-base font-semibold text-ink">{data.proposed_action}</p>
        <p className="text-base text-soft">{data.rationale}</p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-end gap-3 pt-1">
        <label className="flex-1 flex flex-col gap-1">
          <span className="text-base font-mono text-soft">approved by</span>
          <input
            type="text"
            value={approvedBy}
            onChange={(e) => setApprovedBy(e.target.value)}
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-3 py-2 text-base font-mono text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
          />
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handle(false)}
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-4 py-2 text-base font-medium text-ink hover:border-danger hover:text-danger transition-colors disabled:opacity-60"
          >
            Decline
          </button>
          <button
            type="button"
            onClick={() => handle(true)}
            disabled={submitting}
            className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}

// Always fires, in every autonomy stage: anything outside the bounded
// action space, or a hard-invariant mismatch, routes to a human with full
// context instead of a bare alert. Styled distinctly (danger border) from
// the routine approval queue above.
function EscalationCard({
  data,
  onResolve,
}: {
  data: Extract<InterruptData, { kind: "escalation" }>;
  onResolve: (reply: ResumeMessage) => void;
}) {
  const [acknowledgedBy, setAcknowledgedBy] = useState("Neha");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleAcknowledge() {
    if (submitting) return;
    setSubmitting(true);
    onResolve({
      type: "resume",
      kind: "escalation",
      acknowledged_by: acknowledgedBy.trim() || null,
      note: note.trim() || null,
    });
  }

  return (
    <div
      role="alert"
      className="rounded-lg border-2 border-danger bg-danger/10 p-4 sm:p-5 shadow-sm space-y-4"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full bg-danger animate-pulse" />
          <h3 className="font-semibold text-danger uppercase tracking-wide text-base">
            Escalated — needs review
          </h3>
        </div>
        <RiskBadge risk={data.hard_invariant_triggered ? "high" : "medium"} />
      </div>

      <div className="space-y-1">
        <p className="font-mono text-base text-soft">
          {data.po_number} · {data.supplier}
        </p>
        <p className="font-mono text-base font-semibold text-ink">{data.action}</p>
        <p className="text-base text-soft">{data.rationale}</p>
      </div>

      {data.hard_invariant_triggered && (
        <div className="rounded-md border border-danger/40 bg-panel px-3 py-2.5 text-base font-mono text-ink space-y-1">
          <p className="text-danger font-semibold uppercase tracking-wide text-base">hard invariant</p>
          <p>
            PO: {data.ordered_qty} units / {data.ordered_date}
          </p>
          <p>
            reply read as: {data.extracted_qty ?? "—"} units / {data.extracted_date ?? "—"}
          </p>
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-3 pt-1">
        <label className="flex flex-col gap-1">
          <span className="text-base font-mono text-soft">acknowledged by</span>
          <input
            type="text"
            value={acknowledgedBy}
            onChange={(e) => setAcknowledgedBy(e.target.value)}
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-3 py-2 text-base font-mono text-ink focus:outline-none focus:ring-2 focus:ring-danger disabled:opacity-60"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-base font-mono text-soft">resolution note</span>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Called supplier, confirmed real."
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-3 py-2 text-base text-ink focus:outline-none focus:ring-2 focus:ring-danger disabled:opacity-60"
          />
        </label>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleAcknowledge}
          disabled={submitting}
          className="rounded-md bg-danger px-4 py-2 text-base font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-60"
        >
          Acknowledge &amp; resolve
        </button>
      </div>
    </div>
  );
}
