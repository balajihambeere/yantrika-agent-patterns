import type { Decision } from "@/lib/types";

const STYLES: Record<Decision["type"], { border: string; bg: string; label: string }> = {
  independent_action: { border: "border-border", bg: "bg-panel", label: "independent action" },
  unilateral_cross_boundary_act: {
    border: "border-danger/40",
    bg: "bg-danger/10",
    label: "unilateral cross-boundary act",
  },
  coordinated_transfer: { border: "border-safe/40", bg: "bg-safe/10", label: "coordinated transfer" },
  fallback_independent: { border: "border-accent/40", bg: "bg-accent/10", label: "fallback: independent" },
};

export default function DecisionCard({ decision }: { decision: Decision }) {
  const style = STYLES[decision.type];

  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-4 space-y-3`}>
      <div className="flex items-center gap-2 text-base font-mono uppercase tracking-wide text-soft">
        <span>act</span>
        <span className="text-ink font-semibold">{style.label}</span>
      </div>

      {decision.type === "coordinated_transfer" && (
        <p className="font-mono text-base font-semibold text-ink">
          {decision.quantity} units {decision.from_site} → {decision.to_site}
          {decision.rush_order_cancelled ? " · rush order cancelled" : ""}
        </p>
      )}
      {decision.type === "fallback_independent" && (
        <p className="font-mono text-base font-semibold text-danger">
          declined by {decision.declined_by.join(", ")}
        </p>
      )}
      {decision.type === "unilateral_cross_boundary_act" && (
        <p className="font-mono text-base font-semibold text-ink">
          {decision.quantity} units of {decision.sku_family} committed with no human confirmation
        </p>
      )}

      <p className="text-base text-soft">{decision.note}</p>

      {(decision.type === "independent_action" || decision.type === "fallback_independent") && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          <div className="rounded-md border border-border bg-bg/40 px-3 py-2.5">
            <p className="text-base font-mono text-soft uppercase">Pune</p>
            <p className="text-base text-ink font-mono">
              {decision.pune_action.action} · {decision.pune_action.quantity} units
            </p>
          </div>
          <div className="rounded-md border border-border bg-bg/40 px-3 py-2.5">
            <p className="text-base font-mono text-soft uppercase">Nashik</p>
            <p className="text-base text-ink font-mono">
              {decision.nashik_action.action} · {decision.nashik_action.quantity} units
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
