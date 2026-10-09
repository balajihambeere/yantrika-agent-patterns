"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createGovernanceProposal, createOperationalRequest, createReversalCheck } from "@/lib/api";
import type { RequestType, Scenario } from "@/lib/types";
import ScenarioCard from "./ScenarioCard";

const TABS: { key: RequestType; label: string }[] = [
  { key: "operational", label: "Operational Requests" },
  { key: "governance", label: "Governance Proposals" },
  { key: "reversal_check", label: "Reversal Checks" },
];

export default function HomeTabs({ scenarios }: { scenarios: Scenario[] }) {
  const [active, setActive] = useState<RequestType>("operational");
  const [startingId, setStartingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleStart(scenario: Scenario) {
    setError(null);
    setStartingId(scenario.id);
    try {
      let threadId: string;
      if (scenario.request_type === "operational") {
        threadId = (await createOperationalRequest(scenario.payload)).thread_id;
      } else if (scenario.request_type === "governance") {
        threadId = (await createGovernanceProposal(scenario.payload)).thread_id;
      } else {
        threadId = (await createReversalCheck(scenario.payload)).thread_id;
      }
      router.push(`/runs/${threadId}?flow=${scenario.request_type}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start the run.");
      setStartingId(null);
    }
  }

  const visible = scenarios.filter((s) => s.request_type === active);

  return (
    <section className="space-y-4">
      <div className="flex gap-1 border-b border-border overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActive(tab.key)}
            className={`whitespace-nowrap px-3 py-2 text-base font-medium border-b-2 -mb-px transition-colors ${
              active === tab.key ? "border-accent text-accent" : "border-transparent text-soft hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-base text-danger">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {visible.map((scenario) => (
          <ScenarioCard
            key={scenario.id}
            scenario={scenario}
            starting={startingId === scenario.id}
            onStart={() => handleStart(scenario)}
          />
        ))}
        {visible.length === 0 && (
          <p className="text-base text-soft font-mono py-6">No scripted scenarios for this request type.</p>
        )}
      </div>
    </section>
  );
}
