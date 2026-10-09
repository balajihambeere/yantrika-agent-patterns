import Link from "next/link";
import type {
  AppliedState,
  BoundaryCheck,
  EscalationInterruptData,
  OperationalDecision,
  ReversalResult,
  SignoffInterruptData,
  TimelineRow,
  Validation,
} from "@/lib/types";
import Badge from "./Badge";

function Row({
  tone = "neutral",
  label,
  children,
}: {
  tone?: "neutral" | "safe" | "danger" | "accent";
  label: string;
  children: React.ReactNode;
}) {
  const toneClass =
    tone === "safe"
      ? "border-safe/40 bg-safe/10"
      : tone === "danger"
        ? "border-danger/40 bg-danger/10"
        : tone === "accent"
          ? "border-accent/40 bg-accent/10"
          : "border-border bg-panel";
  const labelClass =
    tone === "safe" ? "text-safe" : tone === "danger" ? "text-danger" : tone === "accent" ? "text-accent" : "text-soft";

  return (
    <div className="flex gap-3">
      <div className="pt-1 shrink-0 w-36 text-right">
        <span className={`text-base font-mono uppercase tracking-wide ${labelClass}`}>{label}</span>
      </div>
      <div className={`flex-1 rounded-md border px-3 py-3 ${toneClass}`}>{children}</div>
    </div>
  );
}

function DecisionIdLink({ decisionId }: { decisionId: unknown }) {
  if (typeof decisionId !== "string" || !decisionId) return null;
  return (
    <Link href={`/ledger/${decisionId}`} className="font-mono text-accent hover:underline">
      {decisionId}
    </Link>
  );
}

function NodeRow({ node, data }: { node: string; data: Record<string, unknown> }) {
  switch (node) {
    case "check_boundary": {
      const bc = data.boundary_check as BoundaryCheck;
      return (
        <Row label="check boundary" tone={bc.within_boundary ? "safe" : "accent"}>
          <p className="text-base font-mono text-ink font-semibold">
            within boundary: {String(bc.within_boundary)} <Badge variant={bc.within_boundary ? "safe" : "accent"}>tier {bc.tier}</Badge>
          </p>
          <p className="text-base text-soft mt-1">{bc.reason}</p>
          <p className="text-base text-soft font-mono mt-1">boundary: {bc.boundary_description}</p>
        </Row>
      );
    }
    case "auto_act": {
      const od = data.operational_decision as OperationalDecision;
      return (
        <Row label="auto act" tone="safe">
          <p className="text-base text-ink font-mono">acted autonomously — no human call needed</p>
          <p className="text-base text-soft mt-1">{od.notes}</p>
        </Row>
      );
    }
    case "log_operational":
      return (
        <Row label="log operational" tone="neutral">
          <p className="text-base text-ink">
            five-part record written: <DecisionIdLink decisionId={data.decision_id} />
          </p>
        </Row>
      );
    case "validate_proposal": {
      const v = data.validation as Validation;
      return (
        <Row label="validate proposal" tone={v.approved ? "safe" : "danger"}>
          <p className="text-base font-mono font-semibold text-ink">
            {v.approved ? "all 4 conditions satisfied" : "conditions failed — will be rejected outright"}
          </p>
          {v.failed_conditions.map((reason, i) => (
            <p key={i} className="text-base text-soft mt-1">
              • {reason}
            </p>
          ))}
        </Row>
      );
    }
    case "reject_proposal":
      return (
        <Row label="reject proposal" tone="danger">
          <p className="text-base text-ink">
            deterministic rejection logged — no interrupt ever fired: <DecisionIdLink decisionId={data.decision_id} />
          </p>
        </Row>
      );
    case "apply_tier_change": {
      const applied = data.applied_state as AppliedState;
      return (
        <Row label="apply tier change" tone="accent">
          <p className="text-base font-mono text-ink">
            new policy_version={applied.new_policy_version} · tier {applied.new_tier}
          </p>
          <p className="text-base text-soft mt-1">new boundary: {applied.new_boundary}</p>
        </Row>
      );
    }
    case "log_governance_approved":
      return (
        <Row label="log governance" tone="safe">
          <p className="text-base text-ink">
            approved tier-change record written: <DecisionIdLink decisionId={data.decision_id} />
          </p>
        </Row>
      );
    case "log_governance_declined":
      return (
        <Row label="log governance" tone="danger">
          <p className="text-base text-ink">
            declined-by-approver record written: <DecisionIdLink decisionId={data.decision_id} />
          </p>
        </Row>
      );
    case "evaluate_reversal": {
      const r = data.reversal_result as ReversalResult;
      return (
        <Row label="evaluate reversal" tone={r.fired ? "accent" : "neutral"}>
          <p className="text-base font-mono font-semibold text-ink">fired: {String(r.fired)}</p>
          <p className="text-base text-soft mt-1">{r.explanation}</p>
        </Row>
      );
    }
    case "rollback_tier":
      return (
        <Row label="rollback tier" tone="accent">
          <p className="text-base text-ink">
            automatic rollback logged (no human call involved): <DecisionIdLink decisionId={data.decision_id} />
          </p>
        </Row>
      );
    case "no_rollback":
      return (
        <Row label="no rollback" tone="neutral">
          <p className="text-base text-ink font-mono">trigger did not fire — boundary unchanged</p>
        </Row>
      );
    default:
      return (
        <Row label={node} tone="neutral">
          <pre className="text-base font-mono text-ink whitespace-pre-wrap overflow-x-auto">{JSON.stringify(data, null, 2)}</pre>
        </Row>
      );
  }
}

function InterruptResolvedRow({ row }: { row: Extract<TimelineRow, { kind: "interrupt-resolved" }> }) {
  const label = row.node === "escalate_operational" ? "escalation" : "approver sign-off";
  const detail =
    row.node === "escalate_operational"
      ? (row.data as EscalationInterruptData).action.description
      : String((row.data as SignoffInterruptData).proposal.rationale ?? "tier-change proposal");

  return (
    <Row label={label} tone={row.approved ? "safe" : "danger"}>
      <p className="text-base font-mono font-semibold text-ink">
        {row.approved ? "approved" : "declined"}
        {row.approvedBy ? ` by ${row.approvedBy}` : ""}
      </p>
      <p className="text-base text-soft mt-1">{detail}</p>
      {row.notes && <p className="text-base text-soft mt-1 italic">&quot;{row.notes}&quot;</p>}
    </Row>
  );
}

export default function Timeline({ rows }: { rows: TimelineRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-base text-soft font-mono py-6 text-center">
        No activity yet — start streaming to watch the policy gate work.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {rows.map((row) => {
        switch (row.kind) {
          case "node":
            return <NodeRow key={row.id} node={row.node} data={row.data} />;
          case "interrupt-resolved":
            return <InterruptResolvedRow key={row.id} row={row} />;
        }
      })}
    </div>
  );
}
