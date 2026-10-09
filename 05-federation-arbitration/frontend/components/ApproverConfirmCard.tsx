"use client";

import { useState } from "react";
import type { InterruptData } from "@/lib/types";

// Renders the one, specific named-human confirmation the backend is
// currently waiting on — Neha's or Shalini's. Deliberately has no
// editable "confirmed by" field: who is confirming is fixed by which
// interrupt this is, never a free-text guess the user could get wrong.
export default function ApproverConfirmCard({
  interrupt,
  onResolve,
}: {
  interrupt: InterruptData;
  onResolve: (confirmed: boolean, note: string) => void;
}) {
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handle(confirmed: boolean) {
    if (submitting) return;
    setSubmitting(true);
    onResolve(confirmed, note.trim());
  }

  const siteTag = interrupt.approver_key === "neha" ? "PUNE" : "NASHIK";

  return (
    <div
      role="alert"
      className="rounded-lg border-2 border-accent bg-accent/10 p-5 sm:p-6 shadow-sm space-y-5"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full bg-accent animate-pulse" />
          <h3 className="font-semibold text-accent uppercase tracking-wide text-base">
            Awaiting confirmation from {interrupt.confirmer}
          </h3>
        </div>
        <span className="inline-flex items-center rounded-full border border-accent/40 bg-accent/15 px-2.5 py-1 text-base font-mono uppercase tracking-wide text-accent">
          {siteTag} · {interrupt.role}
        </span>
      </div>

      <div className="space-y-2">
        <p className="text-base text-soft">{interrupt.collision}</p>
        <p className="font-mono text-base font-semibold text-ink">{interrupt.proposed_action}</p>
      </div>

      <div className="flex flex-col gap-3 pt-1">
        <label className="flex flex-col gap-1">
          <span className="text-base font-mono text-soft">note (optional)</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            disabled={submitting}
            rows={2}
            placeholder={`What ${interrupt.confirmer.split(" ")[0]} is weighing...`}
            className="rounded-md border border-border bg-panel px-3 py-2 text-base text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60 resize-none"
          />
        </label>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={() => handle(false)}
            disabled={submitting}
            className="rounded-md border border-border bg-panel px-4 py-2.5 text-base font-medium text-ink hover:border-danger hover:text-danger transition-colors disabled:opacity-60"
          >
            Decline as {interrupt.confirmer}
          </button>
          <button
            type="button"
            onClick={() => handle(true)}
            disabled={submitting}
            className="rounded-md bg-accent px-4 py-2.5 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            Confirm as {interrupt.confirmer}
          </button>
        </div>
      </div>
    </div>
  );
}
