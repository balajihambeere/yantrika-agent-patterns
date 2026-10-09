import { notFound } from "next/navigation";
import { fetchScenario } from "@/lib/api";
import RunView from "@/components/RunView";
import ChatBox from "@/components/ChatBox";
import CollisionBadge from "@/components/CollisionBadge";

export default async function ScenarioRunPage({
  params,
}: {
  params: Promise<{ scenarioId: string }>;
}) {
  const { scenarioId } = await params;

  let scenario;
  try {
    scenario = await fetchScenario(scenarioId);
  } catch {
    scenario = null;
  }

  if (!scenario) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">{scenario.title}</h1>
          <CollisionBadge collision={scenario.expect_collision} />
        </div>
        <p className="text-soft max-w-3xl">{scenario.description}</p>
        <p className="font-mono text-base text-soft">
          sku family {scenario.sku_family} · supplier {scenario.supplier} · connection tier{" "}
          {scenario.connection_tier}
        </p>
      </div>

      <RunView scenarioId={scenario.id} />

      <ChatBox scenarioId={scenario.id} />
    </div>
  );
}
