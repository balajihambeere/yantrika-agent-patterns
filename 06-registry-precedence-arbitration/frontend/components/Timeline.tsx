import type { TimelineRow } from "@/lib/types";

function Row({ label, tone, children }: { label: string; tone?: "safe" | "danger" | "accent"; children: React.ReactNode }) {
  const toneClass =
    tone === "safe"
      ? "border-safe/40 bg-safe/10"
      : tone === "danger"
        ? "border-danger/40 bg-danger/10"
        : tone === "accent"
          ? "border-accent/40 bg-accent/10"
          : "border-border bg-panel";
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 w-40 text-right">
        <span className="font-mono text-base uppercase tracking-wide text-soft break-words">{label}</span>
      </div>
      <div className={`flex-1 rounded-md border px-3 py-2 ${toneClass}`}>{children}</div>
    </div>
  );
}

export default function Timeline({ rows }: { rows: TimelineRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-base text-soft font-mono py-6 text-center">
        No activity yet — submit this claim to watch it race the registry.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((row) => {
        switch (row.kind) {
          case "submit_claim": {
            const c = row.data.claim;
            return (
              <Row key={row.id} label="submit_claim">
                <p className="text-base font-mono text-ink">
                  {c.plant} claims {c.sku} · lot {c.lot_id} · qty {c.quantity_needed}
                </p>
                <p className="text-base text-soft mt-0.5">
                  tier {c.commitment_tier ?? "n/a"} · {c.days_of_cover ?? "n/a"} days cover · requested{" "}
                  {c.requested_at_display}
                </p>
              </Row>
            );
          }
          case "check_registry": {
            const collisions = row.data.collisions;
            return (
              <Row key={row.id} label="check_registry" tone={collisions.length ? "accent" : "safe"}>
                {collisions.length === 0 ? (
                  <p className="text-base text-ink">No open or confirmed claim elsewhere on this lot — clear.</p>
                ) : (
                  <p className="text-base text-ink">
                    Collision detected against:{" "}
                    {collisions.map((c) => `${c.plant} (${c.requested_at_display})`).join(", ")}
                  </p>
                )}
              </Row>
            );
          }
          case "grant":
            return (
              <Row key={row.id} label="grant" tone="safe">
                <p className="text-base text-ink font-mono">{row.data.plant} — {row.data.reason}</p>
              </Row>
            );
          case "arbitrate": {
            const a = row.data;
            return (
              <Row key={row.id} label="arbitrate" tone={a.needs_escalation ? "danger" : "accent"}>
                {a.needs_escalation ? (
                  <p className="text-base text-ink">Cannot resolve — {a.escalation_reason}</p>
                ) : (
                  <ul className="text-base text-ink space-y-1">
                    {a.computation.map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                )}
              </Row>
            );
          }
          case "grant_winner":
            return (
              <Row key={row.id} label="grant_winner" tone="safe">
                <p className="text-base text-ink font-mono">{row.data.plant} — hold confirmed</p>
              </Row>
            );
          case "suggest_alternate_for_loser":
            return (
              <Row key={row.id} label="alternate_cover">
                <ul className="text-base text-ink space-y-1">
                  {row.data.alternate_suggestions.map((s, i) => (
                    <li key={i}>{s.message}</li>
                  ))}
                </ul>
              </Row>
            );
          case "escalation-resolved":
            return (
              <Row key={row.id} label="escalated" tone="danger">
                <p className="text-base text-ink">
                  Resolved by <span className="font-semibold">{row.decision.decided_by}</span>:{" "}
                  {row.decision.note || "no note given"} → <span className="font-semibold">{row.decision.winner_plant}</span>{" "}
                  designated winner by human decision, not by the rulebook.
                </p>
              </Row>
            );
          case "log":
            return (
              <Row key={row.id} label="log">
                <p className="text-base font-mono text-soft">
                  audit entry written ({row.data.type}, claim={row.data.claim_id})
                </p>
              </Row>
            );
          default:
            return null;
        }
      })}
    </div>
  );
}
