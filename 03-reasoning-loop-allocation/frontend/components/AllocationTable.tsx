import type { AllocationResult } from "@/lib/types";
import Badge from "./Badge";

const STATUS_TONE: Record<AllocationResult["status"], "safe" | "accent" | "danger"> = {
  complete: "safe",
  partial: "accent",
  held: "danger",
};

// Renders a recommended or final allocation split. Accepts either the rich
// AllocationResult shape (status/fraction/message) or a plain account ->
// units map, since a human override replaces the system's AllocationResult
// objects with bare unit counts (see DecisionData in lib/types.ts).
export default function AllocationTable({
  allocation,
}: {
  allocation: Record<string, AllocationResult | number>;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-base font-mono">
        <thead>
          <tr className="bg-bg/60 text-soft">
            <th className="text-left px-3.5 py-3 font-medium">account</th>
            <th className="text-right px-3.5 py-3 font-medium">allocated</th>
            <th className="text-right px-3.5 py-3 font-medium">requested</th>
            <th className="text-right px-3.5 py-3 font-medium">status</th>
            <th className="text-left px-3.5 py-3 font-medium">note</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(allocation).map(([account, value]) => {
            const isRich = typeof value === "object";
            const allocated = isRich ? value.allocated_units : value;
            const requested = isRich ? value.requested_units : null;
            return (
              <tr key={account} className="border-t border-border">
                <td className="px-3.5 py-3 text-ink font-semibold">{account}</td>
                <td className="px-3.5 py-3 text-right text-ink">{allocated}</td>
                <td className="px-3.5 py-3 text-right text-soft">{requested ?? "—"}</td>
                <td className="px-3.5 py-3 text-right">
                  {isRich ? <Badge tone={STATUS_TONE[value.status]}>{value.status}</Badge> : <Badge tone="soft">override</Badge>}
                </td>
                <td className="px-3.5 py-3 text-soft">{isRich ? value.message ?? "" : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
