import type { Risk } from "@/lib/types";

const RISK_STYLES: Record<Risk, string> = {
  low: "bg-safe/15 text-safe border-safe/40",
  medium: "bg-accent/15 text-accent border-accent/40",
  high: "bg-accent/15 text-accent border-accent/40",
};

export default function RiskBadge({ risk }: { risk: Risk }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-base font-mono uppercase tracking-wide ${RISK_STYLES[risk]}`}
    >
      {risk} risk
    </span>
  );
}
