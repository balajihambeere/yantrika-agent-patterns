"use client";

import { useState } from "react";
import type { InterruptData } from "@/lib/types";
import RiskBadge from "./RiskBadge";

export default function PendingApprovalCard({
  data,
  onResolve,
}: {
  data: InterruptData;
  onResolve: (approved: boolean, approvedBy: string | null) => void;
}) {
  const [approvedBy, setApprovedBy] = useState("Demo User");
  const [submitting, setSubmitting] = useState(false);

  function handle(approved: boolean) {
    if (submitting) return;
    setSubmitting(true);
    onResolve(approved, approvedBy.trim() || null);
  }

  return (
    <div
      role="alert"
      className="rounded-lg border-2 border-accent bg-accent/10 p-4 sm:p-5 shadow-sm space-y-4"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full bg-accent animate-pulse"
          />
          <h3 className="font-semibold text-accent uppercase tracking-wide text-base">
            Pending Human Approval
          </h3>
        </div>
        <RiskBadge risk={data.risk} />
      </div>

      <div className="space-y-1">
        <p className="font-mono text-base font-semibold text-ink">{data.action}</p>
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
