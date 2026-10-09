import { notFound } from "next/navigation";
import { fetchScenario } from "@/lib/api";
import RunView from "@/components/RunView";
import ChatBox from "@/components/ChatBox";

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
      <div className="space-y-2">
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">{scenario.label}</h1>
        <p className="font-mono text-base text-accent">{scenario.sku}</p>
        <p className="text-soft max-w-2xl">{scenario.description}</p>
        <p className="font-mono text-base text-soft mt-1">
          {scenario.available_units} units available ·{" "}
          {scenario.orders.map((o) => `${o.account} (${o.requested_units})`).join(" · ")}
        </p>
      </div>

      <RunView scenarioId={scenario.id} />

      <ChatBox scenarioId={scenario.id} />
    </div>
  );
}
