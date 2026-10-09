"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchAgents } from "@/lib/api";
import type { Agent } from "@/lib/types";

// Polls /api/agents — the one shared PolicyRegistry every run reads and
// writes — so a tier change from a governance run, or a rollback from a
// reversal check, becomes visible here without a page reload. Seeded
// server-side with `initialAgents` so the registry is present in the
// first HTML response, not only after client JS hydrates.
export default function AgentRegistryPanel({ initialAgents }: { initialAgents: Agent[] }) {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchAgents();
      setAgents(data);
      setError(null);
    } catch {
      setError("Couldn't reach the backend.");
    }
  }, []);

  useEffect(() => {
    // Deliberate mount-time data fetch + poll, not derived render state —
    // `load`'s setState calls land after its own `await`, never synchronously
    // during this effect's commit.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <section className="rounded-lg border border-border bg-panel p-4 space-y-3">
      <h2 className="font-semibold text-base text-soft uppercase tracking-wide">Agent Registry — live</h2>
      {error && <p className="text-base text-danger">{error}</p>}
      <div className="space-y-3">
        {agents.map((a) => (
          <div key={a.agent_id} className="rounded-md border border-border px-3 py-3 text-base space-y-1">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="font-medium">{a.display_name}</span>
              <span className="font-mono text-base text-accent">{a.tier_label.replace(/_/g, " ").toLowerCase()}</span>
            </div>
            <p className="text-base text-soft font-mono">{a.boundary_description}</p>
            <p className="text-base text-soft">
              {a.policy_version} · escalation → {a.escalation_contact}
            </p>
            {a.reversal_trigger_description && (
              <p className="text-base text-soft italic">{a.reversal_trigger_description}</p>
            )}
          </div>
        ))}
        {agents.length === 0 && !error && <p className="text-base text-soft font-mono">Loading…</p>}
      </div>
    </section>
  );
}
