import { notFound } from "next/navigation";
import { fetchScenario } from "@/lib/api";
import OutcomeBadge from "@/components/OutcomeBadge";
import ScenarioRunView from "@/components/ScenarioRunView";

export default async function ScenarioPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let scenario;
  try {
    scenario = await fetchScenario(id);
  } catch {
    scenario = null;
  }

  if (!scenario) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-6">
      <div className="space-y-2">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">{scenario.title}</h1>
          <OutcomeBadge outcome={scenario.expected_outcome} />
        </div>
        <p className="text-soft max-w-3xl">{scenario.summary}</p>
      </div>

      <ScenarioRunView scenario={scenario} />
    </div>
  );
}
