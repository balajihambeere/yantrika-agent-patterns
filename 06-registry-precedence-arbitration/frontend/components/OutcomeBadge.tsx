import type { ExpectedOutcome } from "@/lib/types";

const OUTCOME_STYLES: Record<ExpectedOutcome, string> = {
  granted: "bg-safe/15 text-safe border-safe/40",
  arbitrated: "bg-accent/15 text-accent border-accent/40",
  escalated: "bg-danger/15 text-danger border-danger/40",
};

const OUTCOME_LABELS: Record<ExpectedOutcome, string> = {
  granted: "granted immediately",
  arbitrated: "auto-arbitrated",
  escalated: "escalates to a human",
};

export default function OutcomeBadge({ outcome }: { outcome: ExpectedOutcome }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-base font-mono uppercase tracking-wide ${OUTCOME_STYLES[outcome]}`}
    >
      {OUTCOME_LABELS[outcome]}
    </span>
  );
}
