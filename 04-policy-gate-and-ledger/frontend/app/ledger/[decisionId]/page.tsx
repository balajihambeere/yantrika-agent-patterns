import { notFound } from "next/navigation";
import Link from "next/link";
import { fetchLedgerDecision } from "@/lib/api";

export default async function LedgerDetailPage({
  params,
}: {
  params: Promise<{ decisionId: string }>;
}) {
  const { decisionId } = await params;

  let record;
  try {
    record = await fetchLedgerDecision(decisionId);
  } catch {
    record = null;
  }

  if (!record) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-8 sm:py-10 space-y-6">
      <div>
        <Link href="/" className="font-mono text-base text-soft hover:text-accent transition-colors">
          ← back to ledger
        </Link>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight mt-2">{record.decision_id}</h1>
        <p className="font-mono text-base text-soft mt-1">
          agent {record.agent_id} · tier {record.tier} · {record.record_type} · decided {record.timestamp}
        </p>
        {record.amendment_count > 0 && (
          <p className="text-base text-accent mt-1">
            {record.amendment_count} linked amendment{record.amendment_count === 1 ? "" : "s"} folded in below —
            original record untouched.
          </p>
        )}
      </div>

      <p className="text-base text-soft">
        The direct answer to &quot;walk me through exactly why this decision went the way it did, and which policy
        was actually live at that moment&quot; — one lookup, reconstructed from the append-only decision ledger.
      </p>

      <section className="rounded-lg border border-border bg-panel p-4 sm:p-5 space-y-2">
        <h2 className="font-semibold text-base text-soft uppercase tracking-wide">1 — Inputs actually consulted</h2>
        <pre className="text-base font-mono text-ink whitespace-pre-wrap overflow-x-auto">
          {JSON.stringify(record.inputs, null, 2)}
        </pre>
      </section>

      <section className="rounded-lg border border-border bg-panel p-4 sm:p-5 space-y-2">
        <h2 className="font-semibold text-base text-soft uppercase tracking-wide">2 — Policy &amp; model version in force</h2>
        <p className="text-base font-mono text-ink">policy_version: {record.policy_version}</p>
        <p className="text-base font-mono text-ink">model_version: {record.model_version}</p>
        <p className="text-base text-soft">
          Tied permanently to this record, regardless of what either version has since become — see the Agent
          Registry panel on the home page for what is live right now.
        </p>
      </section>

      <section className="rounded-lg border border-border bg-panel p-4 sm:p-5 space-y-2">
        <h2 className="font-semibold text-base text-soft uppercase tracking-wide">3 — Reasoning path</h2>
        {record.reasoning_path.length === 0 ? (
          <p className="text-base text-soft">(no scored factors recorded for this decision)</p>
        ) : (
          <div className="space-y-3">
            {record.reasoning_path.map((step, i) => (
              <div key={i} className="text-base">
                <span className="font-mono text-accent">{step.factor}</span>
                <span className="font-mono text-soft">
                  {" "}
                  — weight {step.weight} — value {String(step.value)}
                </span>
                <p className="text-base text-soft mt-1">{step.note}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-border bg-panel p-4 sm:p-5 space-y-2">
        <h2 className="font-semibold text-base text-soft uppercase tracking-wide">4 — Human actions</h2>
        {record.human_actions.length === 0 ? (
          <p className="text-base text-soft">(none — this decision was acted on autonomously)</p>
        ) : (
          <div className="space-y-2">
            {record.human_actions.map((h, i) => (
              <p key={i} className="text-base font-mono text-ink">
                {h.when} — {h.who} — {h.action}
                {h.notes ? ` — ${h.notes}` : ""}
              </p>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-safe/40 bg-safe/10 p-4 sm:p-5 space-y-2">
        <h2 className="font-semibold text-base text-safe uppercase tracking-wide">5 — Outcome</h2>
        <pre className="text-base font-mono text-ink whitespace-pre-wrap overflow-x-auto">
          {record.outcome ? JSON.stringify(record.outcome, null, 2) : "(not yet known)"}
        </pre>
      </section>
    </div>
  );
}
