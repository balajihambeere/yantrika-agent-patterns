import { fetchScenarios } from "@/lib/api";
import ScenarioCard from "@/components/ScenarioCard";
import type { Scenario } from "@/lib/types";

export default async function HomePage() {
  let scenarios: Scenario[];
  let supplier = "";
  let image: string | null = null;
  let loadError: string | null = null;

  try {
    const data = await fetchScenarios();
    scenarios = data.scenarios;
    supplier = data.supplier;
    image = data.image;
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
          One shared lot registry, one compiled graph, every claim submission a fresh run against it. Pick a
          scenario to submit its claims — one at a time — against {supplier || "the shared supplier"} and watch
          the registry catch (or not catch) a collision in real time. Two of these scenarios need two separate
          claims, submitted in order, to actually reproduce the collision; most collisions resolve automatically
          via the precedence rulebook, and only a genuine dead heat ever pauses for a human.
        </p>
      </div>

      {loadError ? (
        <div className="rounded-lg border border-danger/40 bg-panel p-4 text-danger">{loadError}</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5">
          {scenarios.map((scenario) => (
            <ScenarioCard key={scenario.id} scenario={scenario} image={image} />
          ))}
        </div>
      )}
    </div>
  );
}
