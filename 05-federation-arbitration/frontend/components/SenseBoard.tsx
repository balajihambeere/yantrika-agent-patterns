import type { LocalRecommendation } from "@/lib/types";

const ACTION_LABELS: Record<string, string> = {
  no_action: "no action",
  surplus_available: "surplus available",
  offer_cross_boundary_transfer: "offer cross-boundary transfer",
  rush_order: "rush order",
};

function SenseColumn({
  label,
  site,
  rec,
}: {
  label: string;
  site: string;
  rec: LocalRecommendation | null;
}) {
  return (
    <div className="flex-1 rounded-md border border-border bg-panel p-4 space-y-3 min-w-0">
      <div className="flex items-center gap-2 text-base font-mono text-soft flex-wrap">
        <span
          aria-hidden
          className={`inline-block h-2 w-2 rounded-full shrink-0 ${rec ? "bg-safe" : "bg-accent animate-pulse"}`}
        />
        <span className="uppercase tracking-wide">{label}</span>
        <span className="text-ink">{site}</span>
      </div>
      {rec ? (
        <div className="space-y-1.5">
          <p className="font-mono text-base font-semibold text-ink">
            {ACTION_LABELS[rec.action] ?? rec.action}
            {rec.quantity > 0 ? ` · ${rec.quantity} units` : ""}
          </p>
          <p className="text-base text-soft">{rec.rationale}</p>
          {rec.touches_other_site && (
            <p className="text-base font-mono text-accent">touches {rec.touches_other_site}</p>
          )}
        </div>
      ) : (
        <p className="text-base text-soft font-mono">sensing…</p>
      )}
    </div>
  );
}

export default function SenseBoard({
  puneRec,
  nashikRec,
}: {
  puneRec: LocalRecommendation | null;
  nashikRec: LocalRecommendation | null;
}) {
  return (
    <div className="space-y-2">
      <p className="text-base font-mono text-soft uppercase tracking-wide">
        sense (parallel — each site sees only its own position)
      </p>
      <div className="flex flex-col sm:flex-row gap-4">
        <SenseColumn label="sense_pune" site="Pune" rec={puneRec} />
        <SenseColumn label="sense_nashik" site="Nashik" rec={nashikRec} />
      </div>
    </div>
  );
}
