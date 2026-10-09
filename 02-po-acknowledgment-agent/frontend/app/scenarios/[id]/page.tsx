import { notFound } from "next/navigation";
import { fetchScenario } from "@/lib/api";
import RunView from "@/components/RunView";
import ChatBox from "@/components/ChatBox";

export default async function ScenarioRunPage({
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
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <div className="space-y-2">
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">{scenario.supplier}</h1>
        <p className="font-mono text-base text-accent">{scenario.po_number}</p>
        <p className="text-soft max-w-2xl">{scenario.summary}</p>
        <p className="font-mono text-base text-soft">
          qty {scenario.ordered_qty} · ordered {scenario.ordered_date} · {scenario.hours_since_po}h since PO
        </p>
      </div>

      <RunView scenarioId={scenario.id} />

      <ChatBox scenarioId={scenario.id} />
    </div>
  );
}
