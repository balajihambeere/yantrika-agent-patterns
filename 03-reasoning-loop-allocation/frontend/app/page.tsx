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
          Allocation Scenarios
        </h1>
        <p className="text-soft max-w-2xl">
          Pick a scripted sensing cycle to start a live run. The reasoning
          loop will sense the competing claims, weigh all five factors,
          recommend an allocation, and escalate to you with the full
          reasoning attached whenever the bounded-autonomy threshold isn&apos;t
          clearly met.
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
