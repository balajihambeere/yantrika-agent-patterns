import type { TimelineRow } from "@/lib/types";
import Badge from "./Badge";
import FactorBreakdown from "./FactorBreakdown";
import AllocationTable from "./AllocationTable";

function Row({
  label,
  tone,
  children,
}: {
  label: string;
  tone: "soft" | "accent" | "safe" | "danger";
  children: React.ReactNode;
}) {
  const border =
    tone === "safe" ? "border-safe/40 bg-safe/10" : tone === "danger" ? "border-danger/40 bg-danger/10" : "border-border bg-panel";
  return (
    <div className="flex gap-3">
      <div className="pt-0.5 shrink-0 w-16 text-right">
        <span className="text-base font-mono uppercase tracking-wide text-soft">{label}</span>
      </div>
      <div className={`flex-1 rounded-md border px-3 py-2.5 space-y-2 ${border}`}>{children}</div>
    </div>
  );
}

function SenseRow({ data }: { data: Extract<TimelineRow, { kind: "sense" }>["data"] }) {
  return (
    <Row label="sense" tone="soft">
      <div className="flex items-center gap-2 text-base font-mono flex-wrap">
        <span className="text-ink font-semibold">{data.label}</span>
        <Badge tone="soft">{data.available_units} units available</Badge>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-0.5 text-base font-mono text-soft">
        {data.orders.map((o) => (
          <div key={o.account} className="flex justify-between gap-2">
            <span className="text-ink truncate">{o.account}</span>
            <span>{o.requested_units} req.</span>
          </div>
        ))}
      </div>
    </Row>
  );
}

function WeighRow({ data }: { data: Extract<TimelineRow, { kind: "weigh" }>["data"] }) {
  return (
    <Row label="weigh" tone="soft">
      <p className="text-base text-soft">
        Every competing order scored against all five factors — deterministic arithmetic, no model.
      </p>
      <FactorBreakdown scores={data} />
    </Row>
  );
}

function RecommendRow({ data }: { data: Extract<TimelineRow, { kind: "recommend" }>["data"] }) {
  return (
    <Row label="recommend" tone={data.requires_human ? "accent" : "safe"}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base font-mono text-soft">
          ranking: <span className="text-ink">{data.ranking.join(" > ")}</span>
        </span>
        <Badge tone={data.clear_agreement ? "safe" : "danger"}>
          {data.clear_agreement ? "factors agree" : "close call"}
        </Badge>
        <Badge tone="soft">exposure Rs.{data.exposure_on_losing_side.toLocaleString("en-IN")}</Badge>
        <Badge tone={data.requires_human ? "accent" : "safe"}>
          {data.requires_human ? "escalate to human" : "act autonomously"}
        </Badge>
      </div>
      <AllocationTable allocation={data.allocation} />
      <p className="text-base text-soft">{data.reason}</p>
    </Row>
  );
}

function ActRow({ data }: { data: Extract<TimelineRow, { kind: "act" }>["data"] }) {
  const tag = data.overridden
    ? `overridden by ${data.decided_by}`
    : data.autonomous
      ? "autonomous — no human call needed"
      : `approved by ${data.decided_by}`;
  return (
    <Row label="act" tone="safe">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base font-mono text-ink font-semibold">{tag}</span>
        {data.overridden && <Badge tone="danger">overridden</Badge>}
      </div>
      <AllocationTable allocation={data.allocation} />
      {data.overridden && data.override_reason && (
        <p className="text-base text-soft">override reason: {data.override_reason}</p>
      )}
    </Row>
  );
}

function LogRow({ data }: { data: Extract<TimelineRow, { kind: "log" }>["data"] }) {
  return (
    <Row label="log" tone="soft">
      <p className="text-base font-mono text-ink">
        entry recorded — {data.reasoning.length} order{data.reasoning.length !== 1 ? "s" : ""} scored across all 5
        factors, full rationale retained, requires_human={String(data.requires_human)}
      </p>
    </Row>
  );
}

function EscalateResolvedRow({ row }: { row: Extract<TimelineRow, { kind: "escalate-resolved" }> }) {
  const resolution = row.resolution;
  const isOverride = resolution.decision === "override";
  return (
    <Row label="escalate" tone={isOverride ? "danger" : "safe"}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base font-mono text-ink font-semibold">{row.data.cycle_label}</span>
        <Badge tone={isOverride ? "danger" : "safe"}>
          {isOverride ? `overridden by ${resolution.decided_by}` : `approved by ${resolution.decided_by}`}
        </Badge>
      </div>
      <p className="text-base text-soft">{row.data.reason}</p>
      {isOverride && (
        <>
          <AllocationTable allocation={resolution.allocation} />
          <p className="text-base text-soft">override reason: {resolution.reason}</p>
        </>
      )}
    </Row>
  );
}

export default function Timeline({ rows }: { rows: TimelineRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-base text-soft font-mono py-6 text-center">
        No activity yet — start a run to watch the reasoning loop work.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((row) => {
        switch (row.kind) {
          case "sense":
            return <SenseRow key={row.id} data={row.data} />;
          case "weigh":
            return <WeighRow key={row.id} data={row.data} />;
          case "recommend":
            return <RecommendRow key={row.id} data={row.data} />;
          case "act":
            return <ActRow key={row.id} data={row.data} />;
          case "log":
            return <LogRow key={row.id} data={row.data} />;
          case "escalate-resolved":
            return <EscalateResolvedRow key={row.id} row={row} />;
        }
      })}
    </div>
  );
}
