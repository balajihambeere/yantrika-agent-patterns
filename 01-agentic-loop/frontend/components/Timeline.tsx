import type { TimelineRow } from "@/lib/types";
import RiskBadge from "./RiskBadge";

function ObserveRow({ data }: { data: Extract<TimelineRow, { kind: "observe" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-1 shrink-0 font-mono text-base text-soft w-16 text-right">
        t+{data.minutes_after_start}m
      </div>
      <div className="flex-1 rounded-md border border-border bg-panel px-3 py-2.5">
        <div className="flex items-center gap-2 text-base font-mono text-soft">
          <span className="uppercase tracking-wide text-soft">observe</span>
          <span className="text-ink">balance {data.balance}</span>
        </div>
        <p className="text-base text-ink mt-1">{data.last_transaction}</p>
      </div>
    </div>
  );
}

function DecideRow({ data }: { data: Extract<TimelineRow, { kind: "decide" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-1 shrink-0 w-16" />
      <div className="flex-1 rounded-md border border-border bg-panel px-3 py-2.5">
        <div className="flex items-center gap-2 text-base font-mono text-soft flex-wrap">
          <span className="uppercase tracking-wide text-soft">decide</span>
          <span className="text-ink font-semibold">{data.action}</span>
          <RiskBadge risk={data.risk} />
        </div>
        <p className="text-base text-soft mt-1">{data.rationale}</p>
      </div>
    </div>
  );
}

function ActRow({ data }: { data: Extract<TimelineRow, { kind: "act" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-1 shrink-0 w-16" />
      <div className="flex-1 rounded-md border border-safe/40 bg-safe/10 px-3 py-2.5">
        <div className="flex items-center gap-2 text-base font-mono text-soft">
          <span className="uppercase tracking-wide text-safe">act</span>
        </div>
        <p className="text-base text-ink font-mono mt-1">{data.outcome}</p>
      </div>
    </div>
  );
}

function InterruptResolvedRow({
  row,
}: {
  row: Extract<TimelineRow, { kind: "interrupt-resolved" }>;
}) {
  return (
    <div className="flex gap-3">
      <div className="pt-1 shrink-0 w-16" />
      <div
        className={`flex-1 rounded-md border px-3 py-2.5 ${
          row.approved ? "border-safe/40 bg-safe/10" : "border-danger/40 bg-danger/10"
        }`}
      >
        <div className="flex items-center gap-2 text-base font-mono flex-wrap">
          <span className="uppercase tracking-wide text-soft">human review</span>
          <span className="text-ink font-semibold">{row.data.action}</span>
          <RiskBadge risk={row.data.risk} />
          <span className={row.approved ? "text-safe" : "text-danger"}>
            {row.approved ? "approved" : "declined"}
            {row.approvedBy ? ` by ${row.approvedBy}` : ""}
          </span>
        </div>
        <p className="text-base text-soft mt-1">{row.data.rationale}</p>
      </div>
    </div>
  );
}

export default function Timeline({ rows }: { rows: TimelineRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-base text-soft font-mono py-6 text-center">
        No activity yet — start a run to watch the agent work.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((row) => {
        switch (row.kind) {
          case "observe":
            return <ObserveRow key={row.id} data={row.data} />;
          case "decide":
            return <DecideRow key={row.id} data={row.data} />;
          case "act":
            return <ActRow key={row.id} data={row.data} />;
          case "interrupt-resolved":
            return <InterruptResolvedRow key={row.id} row={row} />;
        }
      })}
    </div>
  );
}
