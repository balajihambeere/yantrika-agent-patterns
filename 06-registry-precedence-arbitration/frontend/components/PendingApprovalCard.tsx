"use client";

import { useState } from "react";
import type { InterruptData } from "@/lib/types";

export default function PendingApprovalCard({
  data,
  onResolve,
}: {
  data: InterruptData;
  onResolve: (winnerPlant: string, decidedBy: string, note: string) => void;
}) {
  const [winnerPlant, setWinnerPlant] = useState(data.competing_claims[0]?.plant ?? "");
  const [decidedBy, setDecidedBy] = useState("Kavita Iyer");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleSubmit() {
    if (submitting || !winnerPlant) return;
    setSubmitting(true);
    onResolve(winnerPlant, decidedBy.trim() || "Kavita Iyer's team", note.trim());
  }

  return (
    <div
      role="alert"
      className="rounded-lg border-2 border-danger bg-danger/10 p-4 sm:p-5 shadow-sm space-y-4"
    >
      <div className="flex items-center gap-2">
        <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full bg-danger animate-pulse" />
        <h3 className="font-semibold text-danger uppercase tracking-wide text-base">
          Genuine dead heat — escalated to {data.escalated_to}
        </h3>
      </div>

      <p className="text-base text-soft">{data.reason}</p>

      <div className="space-y-2">
        <p className="text-base font-mono text-soft uppercase tracking-wide">competing claims</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {data.competing_claims.map((c) => (
            <label
              key={c.plant}
              className={`flex items-start gap-2 rounded-md border px-3 py-2 cursor-pointer transition-colors ${
                winnerPlant === c.plant ? "border-accent bg-accent/10" : "border-border bg-panel"
              }`}
            >
              <input
                type="radio"
                name="winner_plant"
                value={c.plant}
                checked={winnerPlant === c.plant}
                onChange={() => setWinnerPlant(c.plant)}
                disabled={submitting}
                className="mt-1"
              />
              <span className="text-base">
                <span className="font-semibold text-ink">{c.plant}</span>
                <span className="block font-mono text-base text-soft">
                  tier {c.commitment_tier ?? "—"} · {c.days_of_cover ?? "—"} days cover · requested{" "}
                  {c.requested_at_display}
                </span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-base font-mono text-soft">decided by</span>
          <input
            type="text"
            value={decidedBy}
            onChange={(e) => setDecidedBy(e.target.value)}
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-3 py-2 text-base font-mono text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-base font-mono text-soft">note (goes in the audit log)</span>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="why this plant should win the tie"
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-3 py-2 text-base text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
          />
        </label>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting || !winnerPlant}
          className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-60"
        >
          {submitting ? "Submitting decision…" : `Designate ${winnerPlant || "…"} as winner`}
        </button>
      </div>
    </div>
  );
}
