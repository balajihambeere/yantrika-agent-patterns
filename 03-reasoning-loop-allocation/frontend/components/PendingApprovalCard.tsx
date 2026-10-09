"use client";

import { useState } from "react";
import type { InterruptData, ResumeMessage } from "@/lib/types";
import Badge from "./Badge";
import FactorBreakdown from "./FactorBreakdown";
import AllocationTable from "./AllocationTable";

export default function PendingApprovalCard({
  data,
  onResolve,
}: {
  data: InterruptData;
  onResolve: (resolution: ResumeMessage) => void;
}) {
  const [decidedBy, setDecidedBy] = useState("Demo User");
  const [mode, setMode] = useState<"review" | "override">("review");
  const [overrideAllocation, setOverrideAllocation] = useState<Record<string, number>>(() => {
    const initial: Record<string, number> = {};
    for (const [account, result] of Object.entries(data.recommended_allocation)) {
      initial[account] = result.allocated_units;
    }
    return initial;
  });
  const [overrideReason, setOverrideReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function submitApprove() {
    if (submitting) return;
    setSubmitting(true);
    onResolve({ type: "resume", decision: "approve", decided_by: decidedBy.trim() || "unknown" });
  }

  function submitOverride() {
    if (submitting) return;
    setSubmitting(true);
    onResolve({
      type: "resume",
      decision: "override",
      decided_by: decidedBy.trim() || "unknown",
      allocation: overrideAllocation,
      reason: overrideReason.trim() || "No reason given.",
    });
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
            Pending Human Decision
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={data.clear_agreement ? "safe" : "danger"}>
            {data.clear_agreement ? "factors agree" : "close call"}
          </Badge>
          <Badge tone="accent">exposure Rs.{data.exposure_on_losing_side.toLocaleString("en-IN")}</Badge>
        </div>
      </div>

      <div className="space-y-1">
        <p className="font-mono text-base font-semibold text-ink">{data.cycle_label}</p>
        <p className="text-base text-soft">
          Didn&apos;t clear the bounded-autonomy threshold: {data.reason}
        </p>
      </div>

      <div className="space-y-2">
        <h4 className="text-base font-mono uppercase tracking-wide text-soft">
          full weighted reasoning — every factor, every order
        </h4>
        <FactorBreakdown scores={data.reasoning} />
      </div>

      <div className="space-y-2">
        <h4 className="text-base font-mono uppercase tracking-wide text-soft">
          system&apos;s recommended allocation
        </h4>
        <AllocationTable allocation={data.recommended_allocation} />
      </div>

      <div className="flex flex-col gap-3 pt-1 border-t border-accent/30">
        <label className="flex flex-col gap-1 pt-3 sm:w-64">
          <span className="text-base font-mono text-soft">decided by</span>
          <input
            type="text"
            value={decidedBy}
            onChange={(e) => setDecidedBy(e.target.value)}
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-3 py-2 text-base font-mono text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
          />
        </label>

        {mode === "review" ? (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={submitApprove}
              disabled={submitting}
              className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-60"
            >
              Approve recommendation
            </button>
            <button
              type="button"
              onClick={() => setMode("override")}
              disabled={submitting}
              className="rounded-md border border-border bg-panel px-4 py-2 text-base font-medium text-ink hover:border-danger hover:text-danger transition-colors disabled:opacity-60"
            >
              Override with a different split
            </button>
          </div>
        ) : (
          <div className="space-y-3 rounded-md border border-border bg-panel p-3">
            <p className="text-base font-mono uppercase tracking-wide text-soft">override allocation</p>
            <div className="space-y-2">
              {Object.keys(overrideAllocation).map((account) => (
                <label key={account} className="flex items-center justify-between gap-3 text-base">
                  <span className="font-mono text-ink">{account}</span>
                  <input
                    type="number"
                    min={0}
                    value={overrideAllocation[account]}
                    onChange={(e) =>
                      setOverrideAllocation((prev) => ({
                        ...prev,
                        [account]: Number(e.target.value),
                      }))
                    }
                    disabled={submitting}
                    className="w-28 rounded-md border border-border bg-bg px-2 py-1 text-right font-mono text-base text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
                  />
                </label>
              ))}
            </div>
            <label className="flex flex-col gap-1">
              <span className="text-base font-mono text-soft">reason for overriding</span>
              <textarea
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                disabled={submitting}
                rows={2}
                placeholder="e.g. Konkan Precision's plant is mid-shutdown and won't consume this shipment for a week."
                className="rounded-md border border-border bg-bg px-3 py-2 text-base text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
              />
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode("review")}
                disabled={submitting}
                className="rounded-md border border-border bg-panel px-4 py-2 text-base font-medium text-ink hover:border-accent transition-colors disabled:opacity-60"
              >
                Back
              </button>
              <button
                type="button"
                onClick={submitOverride}
                disabled={submitting}
                className="rounded-md bg-danger px-4 py-2 text-base font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-60"
              >
                Submit override
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
