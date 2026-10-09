import { fetchScenarios } from "@/lib/api";
import ScenarioCard from "@/components/ScenarioCard";
import type { Scenario } from "@/lib/types";

export default async function HomePage() {
  let scenarios: Scenario[];
  let loadError: string | null = null;

  try {
    scenarios = await fetchScenarios();
  } catch {
    scenarios = [];
    loadError =
      "Couldn't reach the backend at the configured NEXT_PUBLIC_API_URL. Make sure the FastAPI server is running on port 8000.";
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10">
      <div className="mb-8 space-y-2">
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">Scenarios</h1>
        <p className="text-soft max-w-2xl">
          Two site-scoped agents — Pune&apos;s and Nashik&apos;s allocation agents — sense their own
          plant&apos;s position in parallel. When their recommendations would jointly over-commit the
          same resource, the run pauses for two separate, named-human confirmations — Neha Joshi
          (Pune), then Shalini Rao (Nashik) — before anything crosses the boundary.
        </p>
      </div>

      {loadError ? (
        <div className="rounded-lg border border-danger/40 bg-panel p-4 text-danger">{loadError}</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
          {scenarios.map((scenario) => (
            <ScenarioCard key={scenario.id} scenario={scenario} />
          ))}
        </div>
      )}
    </div>
  );
}
