import type { Scenario } from "@/lib/types";
import Badge from "./Badge";

const REQUEST_TYPE_LABEL: Record<Scenario["request_type"], string> = {
  operational: "operational",
  governance: "governance",
  reversal_check: "reversal check",
};

export default function ScenarioCard({
  scenario,
  starting,
  onStart,
}: {
  scenario: Scenario;
  starting: boolean;
  onStart: () => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-panel p-4 sm:p-5 space-y-3 flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-snug">{scenario.title}</h3>
        <Badge>{REQUEST_TYPE_LABEL[scenario.request_type]}</Badge>
      </div>
      <p className="text-base text-soft flex-1">{scenario.description}</p>
      <p className="font-mono text-base text-accent">agent: {scenario.payload.agent_id}</p>
      <button
        type="button"
        onClick={onStart}
        disabled={starting}
        className="self-start rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {starting ? "Starting…" : "Start"}
      </button>
    </div>
  );
}
