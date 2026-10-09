import type { FactorScores } from "@/lib/types";

const FACTOR_COLUMNS: { key: keyof FactorScores["factor_points"]; label: string }[] = [
  { key: "contract_penalty", label: "Contract Penalty" },
  { key: "downstream_impact", label: "Downstream Impact" },
  { key: "strategic_trajectory", label: "Strategic Trajectory" },
  { key: "replenishment_confidence", label: "Replenishment Urgency" },
  { key: "cost_to_close_gap", label: "Cost to Close Gap" },
];

// Renders the full weighted five-factor breakdown for every competing
// order in a cycle — the substantive, architecturally interesting payload
// of this example. Each cell shows the weighted points contributed and,
// beneath it, the 0-100 percentile it was derived from.
export default function FactorBreakdown({ scores }: { scores: FactorScores[] }) {
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-base font-mono">
          <thead>
            <tr className="bg-bg/60 text-soft">
              <th className="text-left px-3.5 py-3 font-medium">account</th>
              <th className="text-right px-3.5 py-3 font-medium">req.</th>
              {FACTOR_COLUMNS.map((col) => (
                <th key={col.key} className="text-right px-3.5 py-3 font-medium whitespace-nowrap">
                  {col.label}
                </th>
              ))}
              <th className="text-right px-3.5 py-3 font-medium">weighted total</th>
            </tr>
          </thead>
          <tbody>
            {scores.map((s) => (
              <tr key={s.account} className="border-t border-border">
                <td className="px-3.5 py-3 text-ink font-semibold">{s.account}</td>
                <td className="px-3.5 py-3 text-right text-soft">{s.requested_units}</td>
                {FACTOR_COLUMNS.map((col) => (
                  <td key={col.key} className="px-3.5 py-3 text-right">
                    <div className="text-ink">{s.factor_points[col.key].toFixed(1)}</div>
                    <div className="text-soft mt-1">{s.factor_percentiles[col.key].toFixed(0)}/100</div>
                  </td>
                ))}
                <td className="px-3.5 py-3 text-right text-accent font-semibold">
                  {s.weighted_total.toFixed(1)}/100
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-2">
        {scores.map((s) => (
          <details key={s.account} className="group rounded-md border border-border bg-bg/40 px-3.5 py-2.5">
            <summary className="cursor-pointer text-base font-mono text-soft">
              rationale — <span className="text-ink">{s.account}</span>
            </summary>
            <ul className="mt-2 space-y-1.5 text-base text-soft list-disc list-inside">
              {s.rationale.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </div>
  );
}
