import type { TimelineRow } from "@/lib/types";
import RiskBadge from "./RiskBadge";

function TriggerRow({ data }: { data: Extract<TimelineRow, { kind: "trigger" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 font-mono text-base text-soft w-20 text-right">
        +{data.hours_since_po}h
      </div>
      <div className="flex-1 rounded-md border border-border bg-panel px-3 py-2">
        <div className="flex items-center gap-2 text-base font-mono text-soft flex-wrap">
          <span className="uppercase tracking-wide text-soft">trigger</span>
          <span className="text-ink">{data.reason.replace(/_/g, " ")}</span>
        </div>
        {data.matched_via && (
          <p className="text-base text-ink mt-0.5">matched via {data.matched_via.replace(/_/g, " ")}</p>
        )}
      </div>
    </div>
  );
}

function PerceiveRow({ data }: { data: Extract<TimelineRow, { kind: "perceive" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 w-20" />
      <div className="flex-1 rounded-md border border-border bg-panel px-3 py-2">
        <div className="flex items-center gap-2 text-base font-mono text-soft flex-wrap">
          <span className="uppercase tracking-wide text-soft">perceive</span>
          <span className="text-ink font-semibold">{data.situation}</span>
          <span className="text-soft">confidence {data.confidence.toFixed(2)}</span>
          {data.source === "attachment" && <span className="text-soft">(attachment scan)</span>}
        </div>
        <p className="text-base text-soft mt-0.5">{data.notes}</p>
      </div>
    </div>
  );
}

function DecideRow({ data }: { data: Extract<TimelineRow, { kind: "decide" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 w-20" />
      <div className="flex-1 rounded-md border border-border bg-panel px-3 py-2">
        <div className="flex items-center gap-2 text-base font-mono text-soft flex-wrap">
          <span className="uppercase tracking-wide text-soft">decide</span>
          <span className="text-ink font-semibold">{data.action}</span>
          <RiskBadge risk={data.risk} />
          {data.hard_invariant_triggered && (
            <span className="text-danger font-semibold">hard invariant</span>
          )}
        </div>
        <p className="text-base text-soft mt-0.5">{data.rationale}</p>
      </div>
    </div>
  );
}

function ActRow({ data }: { data: Extract<TimelineRow, { kind: "act" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 w-20" />
      <div className="flex-1 rounded-md border border-safe/40 bg-safe/10 px-3 py-2">
        <div className="flex items-center gap-2 text-base font-mono text-soft">
          <span className="uppercase tracking-wide text-safe">act</span>
          {data.approved_by && <span className="text-soft">by {data.approved_by}</span>}
        </div>
        <p className="text-base text-ink font-mono mt-0.5">{data.outcome}</p>
      </div>
    </div>
  );
}

function LogRow({ data }: { data: Extract<TimelineRow, { kind: "log" }>["data"] }) {
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 w-20" />
      <div className="flex-1 rounded-md border border-border bg-bg/60 px-3 py-2">
        <div className="flex items-center gap-2 text-base font-mono text-soft">
          <span className="uppercase tracking-wide text-soft">log</span>
          <span className="text-ink">{data.timestamp}</span>
        </div>
        <p className="text-base text-soft mt-0.5 font-mono">
          {data.action_result?.outcome ??
            (data.escalation_result
              ? `escalation acknowledged by ${data.escalation_result.acknowledged_by ?? "unknown"}${
                  data.escalation_result.note ? `: ${data.escalation_result.note}` : ""
                }`
              : "recorded")}
        </p>
      </div>
    </div>
  );
}

function InterruptResolvedRow({
  row,
}: {
  row: Extract<TimelineRow, { kind: "interrupt-resolved" }>;
}) {
  const data = row.data;
  const isApproval = data.kind === "action_approval";
  const action = data.kind === "action_approval" ? data.proposed_action : data.action;
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 w-20" />
      <div
        className={`flex-1 rounded-md border px-3 py-2 ${
          isApproval ? "border-accent/40 bg-accent/10" : "border-danger/40 bg-danger/10"
        }`}
      >
        <div className="flex items-center gap-2 text-base font-mono flex-wrap">
          <span className="uppercase tracking-wide text-soft">
            {isApproval ? "approval resolved" : "escalation resolved"}
          </span>
          <span className="text-ink font-semibold">{action}</span>
        </div>
        <p className="text-base text-soft mt-0.5">{data.rationale}</p>
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
          case "trigger":
            return <TriggerRow key={row.id} data={row.data} />;
          case "perceive":
            return <PerceiveRow key={row.id} data={row.data} />;
          case "decide":
            return <DecideRow key={row.id} data={row.data} />;
          case "act":
            return <ActRow key={row.id} data={row.data} />;
          case "log":
            return <LogRow key={row.id} data={row.data} />;
          case "interrupt-resolved":
            return <InterruptResolvedRow key={row.id} row={row} />;
        }
      })}
    </div>
  );
}
