import Link from "next/link";
import type { Scenario } from "@/lib/types";

export default function ScenarioCard({ scenario }: { scenario: Scenario }) {
  return (
    <Link
      href={`/runs/${scenario.id}`}
      className="group block rounded-lg border border-border bg-panel overflow-hidden hover:border-accent transition-colors p-5 space-y-3"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-semibold leading-snug group-hover:text-accent transition-colors">
          {scenario.label}
        </h2>
      </div>
      <p className="font-mono text-base text-accent">{scenario.sku}</p>
      <p className="text-base text-soft">{scenario.description}</p>
      <div className="pt-1 space-y-1">
        <p className="text-base font-mono uppercase tracking-wide text-soft">
          competing claims · {scenario.available_units} units available
        </p>
        <dl className="space-y-0.5">
          {scenario.orders.map((order) => (
            <div key={order.account} className="flex items-baseline justify-between gap-3 text-base font-mono">
              <dt className="text-ink truncate">{order.account}</dt>
              <dd className="text-soft shrink-0">{order.requested_units} req.</dd>
            </div>
          ))}
        </dl>
      </div>
    </Link>
  );
}
