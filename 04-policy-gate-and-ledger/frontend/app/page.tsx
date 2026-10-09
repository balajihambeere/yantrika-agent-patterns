import { fetchAgents, fetchLedger, fetchScenarios } from "@/lib/api";
import HomeTabs from "@/components/HomeTabs";
import AgentRegistryPanel from "@/components/AgentRegistryPanel";
import LedgerPanel from "@/components/LedgerPanel";
import type { Agent, LedgerListResponse, Scenario } from "@/lib/types";

export default async function HomePage() {
  let scenarios: Scenario[];
  let agents: Agent[];
  let ledger: LedgerListResponse | null;
  let loadError: string | null = null;

  try {
    [scenarios, agents, ledger] = await Promise.all([fetchScenarios(), fetchAgents(), fetchLedger(25)]);
  } catch {
    scenarios = [];
    agents = [];
    ledger = null;
    loadError =
      "Couldn't reach the backend at the configured NEXT_PUBLIC_API_URL. Make sure the FastAPI server is running on port 8000.";
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-10">
      <div className="space-y-2">
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">Policy Gate &amp; Decision Ledger</h1>
        <p className="text-soft max-w-3xl">
          One gate, three request types. Operational actions auto-act inside an agent&apos;s boundary or escalate
          to a named human outside it. Governance proposals are validated by policy-as-code before a named
          approver ever sees one. Reversal checks roll a tier back automatically — no interrupt, ever. Every
          branch writes exactly one five-part record to the shared ledger below.
        </p>
      </div>

      {loadError ? (
        <div className="rounded-lg border border-danger/40 bg-panel p-4 text-danger">{loadError}</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-6 items-start">
          <HomeTabs scenarios={scenarios} />
          <AgentRegistryPanel initialAgents={agents} />
        </div>
      )}

      <LedgerPanel initialData={ledger} />
    </div>
  );
}
