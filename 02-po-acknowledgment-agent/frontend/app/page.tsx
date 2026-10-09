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
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
          PO Scenarios
        </h1>
        <p className="text-soft max-w-2xl">
          Pick a scripted purchase-order scenario to start a live run. The
          agent will trigger on a supplier reply (or 48 hours of silence),
          perceive what it means, decide one of four pre-approved actions,
          and either act directly or pause for a human — always, for
          escalations; only while supervised, for routine actions.
        </p>
      </div>

      {loadError ? (
        <div className="rounded-lg border border-danger/40 bg-panel p-4 text-danger">
          {loadError}
        </div>
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
