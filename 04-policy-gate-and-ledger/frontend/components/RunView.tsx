"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { getWsUrl } from "@/lib/api";
import type {
  AppliedState,
  Approval,
  DoneData,
  InterruptData,
  OperationalDecision,
  ResumeMessage,
  ReversalResult,
  ServerMessage,
  TimelineRow,
  Validation,
} from "@/lib/types";
import Timeline from "./Timeline";
import PendingApprovalCard from "./PendingApprovalCard";

type Status = "idle" | "connecting" | "running" | "awaiting-approval" | "done" | "error";

function DoneSummary({ data }: { data: DoneData }) {
  const od = data.operational_decision as OperationalDecision | null | undefined;
  const val = data.validation as Validation | null | undefined;
  const appr = data.approval as Approval | null | undefined;
  const applied = data.applied_state as AppliedState | null | undefined;
  const rev = data.reversal_result as ReversalResult | null | undefined;

  const lines: string[] = [];
  let tone: "safe" | "danger" = "safe";

  if (od) {
    lines.push(od.acted ? `Acted${od.acted_by ? ` (by ${od.acted_by})` : ""}` : "Not acted — declined");
    if (od.escalated) {
      lines.push(`Escalated — ${od.approved_by ? `resolved by ${od.approved_by}` : "no resolution recorded"}`);
    }
    if (!od.acted) tone = "danger";
  }
  if (val) {
    lines.push(
      val.approved
        ? "All 4 policy-as-code conditions satisfied"
        : `Rejected by policy engine — ${val.failed_conditions.length} condition(s) failed`
    );
    if (!val.approved) tone = "danger";
  }
  if (appr) {
    lines.push(appr.approved ? `Approved by ${appr.approved_by}` : `Declined by ${appr.approved_by}`);
    if (!appr.approved) tone = "danger";
  }
  if (applied) {
    lines.push(`New boundary: ${applied.new_boundary} (policy ${applied.new_policy_version})`);
  }
  if (rev) {
    lines.push(rev.fired ? "Reversal trigger FIRED — automatic rollback" : "Reversal trigger did not fire — boundary unchanged");
  }

  return (
    <div
      className={`rounded-lg border p-4 space-y-2 ${
        tone === "danger" ? "border-danger/40 bg-danger/10" : "border-safe/40 bg-safe/10"
      }`}
    >
      <p className={`font-semibold ${tone === "danger" ? "text-danger" : "text-safe"}`}>Run complete</p>
      {lines.map((line, i) => (
        <p key={i} className="text-base font-mono text-ink">
          {line}
        </p>
      ))}
      {data.decision_id ? (
        <p className="text-base font-mono text-soft pt-1">
          Logged as{" "}
          <Link href={`/ledger/${data.decision_id}`} className="text-accent hover:underline">
            {data.decision_id}
          </Link>{" "}
          in the decision ledger.
        </p>
      ) : (
        <p className="text-base font-mono text-soft pt-1">
          No ledger record written for this outcome (e.g. a reversal check whose trigger didn&apos;t fire).
        </p>
      )}
    </div>
  );
}

export default function RunView({
  threadId,
  flow,
  onDone,
}: {
  threadId: string;
  flow: string;
  onDone?: (data: DoneData) => void;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [rows, setRows] = useState<TimelineRow[]>([]);
  const [pendingInterrupt, setPendingInterrupt] = useState<{
    node: "escalate_operational" | "approver_signoff";
    data: InterruptData;
  } | null>(null);
  const [doneData, setDoneData] = useState<DoneData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const settledRef = useRef(false);
  const idCounterRef = useRef(0);
  const onDoneRef = useRef(onDone);
  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  function nextId(prefix: string): string {
    idCounterRef.current += 1;
    return `${prefix}-${idCounterRef.current}`;
  }

  const closeSocket = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.close();
      } catch {
        // socket already closing/closed — nothing to do
      }
    }
  }, []);

  useEffect(() => {
    // Close the socket if the user navigates away mid-run.
    return () => closeSocket();
  }, [closeSocket]);

  const start = useCallback(() => {
    setStatus("connecting");
    setErrorMessage(null);
    setDoneData(null);
    setPendingInterrupt(null);
    setRows([]);
    settledRef.current = false;
    idCounterRef.current = 0;

    try {
      const ws = new WebSocket(getWsUrl(threadId));
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("running");
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        let message: ServerMessage;
        try {
          message = JSON.parse(event.data) as ServerMessage;
        } catch {
          return;
        }

        switch (message.type) {
          case "node":
            // escalate_operational / approver_signoff's own return value is
            // already fully represented by the interrupt + resume exchange
            // below — skip it here to avoid showing the same decision twice.
            if (message.node === "escalate_operational" || message.node === "approver_signoff") break;
            setRows((prev) => [...prev, { kind: "node", id: nextId("n"), node: message.node, data: message.data }]);
            break;
          case "interrupt":
            setPendingInterrupt({ node: message.node, data: message.data });
            setStatus("awaiting-approval");
            break;
          case "done":
            settledRef.current = true;
            setDoneData(message.data);
            setStatus("done");
            onDoneRef.current?.(message.data);
            break;
          case "error":
            settledRef.current = true;
            setErrorMessage(message.data.message);
            setStatus("error");
            break;
        }
      };

      ws.onerror = () => {
        if (settledRef.current) return;
        settledRef.current = true;
        setErrorMessage("WebSocket connection error.");
        setStatus("error");
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (settledRef.current) return;
        settledRef.current = true;
        setErrorMessage("Connection to the backend closed unexpectedly before the run finished.");
        setStatus("error");
      };
    } catch (err) {
      settledRef.current = true;
      setErrorMessage(err instanceof Error ? err.message : "Failed to start the run.");
      setStatus("error");
    }
  }, [threadId]);

  const resolveInterrupt = useCallback(
    (approved: boolean, approvedBy: string | null, notes: string) => {
      const ws = wsRef.current;
      const interruptInfo = pendingInterrupt;
      if (!ws || !interruptInfo) return;

      setRows((prev) => [
        ...prev,
        {
          kind: "interrupt-resolved",
          id: nextId("int"),
          node: interruptInfo.node,
          data: interruptInfo.data,
          approved,
          approvedBy,
          notes,
        },
      ]);
      setPendingInterrupt(null);
      setStatus("running");

      const reply: ResumeMessage = { type: "resume", approved, approved_by: approvedBy, notes };
      try {
        ws.send(JSON.stringify(reply));
      } catch {
        settledRef.current = true;
        setErrorMessage("Failed to send your decision to the backend.");
        setStatus("error");
      }
    },
    [pendingInterrupt]
  );

  const isBusy = status === "connecting" || status === "running" || status === "awaiting-approval";

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="font-semibold text-lg">Run &mdash; {flow.replace(/_/g, " ")}</h2>

        {status === "idle" && (
          <button
            type="button"
            onClick={start}
            className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity"
          >
            Start streaming
          </button>
        )}
        {isBusy && (
          <button
            type="button"
            disabled
            className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent opacity-50"
          >
            {status === "connecting" && "Connecting…"}
            {status === "running" && "Running…"}
            {status === "awaiting-approval" && "Awaiting sign-off…"}
          </button>
        )}
        {(status === "done" || status === "error") && (
          <Link
            href="/"
            className="rounded-md border border-border bg-panel px-4 py-2 text-base font-medium text-ink hover:border-accent hover:text-accent transition-colors"
          >
            ← start another request
          </Link>
        )}
      </div>

      {status === "error" && errorMessage && (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-base text-danger">
          <span className="font-semibold">Run stopped: </span>
          {errorMessage}
        </div>
      )}

      {pendingInterrupt && (
        <PendingApprovalCard node={pendingInterrupt.node} data={pendingInterrupt.data} onResolve={resolveInterrupt} />
      )}

      {status === "done" && doneData && <DoneSummary data={doneData} />}

      <div className="rounded-lg border border-border bg-bg/40 p-3 sm:p-4">
        <Timeline rows={rows} />
      </div>
    </section>
  );
}
