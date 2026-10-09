"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getClaimWsUrl, submitClaim, type ClaimFields } from "@/lib/api";
import type { InterruptData, LogEntry, ResumeMessage, ScenarioClaim, ServerMessage, TimelineRow } from "@/lib/types";
import Timeline from "./Timeline";
import PendingApprovalCard from "./PendingApprovalCard";

type Status = "idle" | "connecting" | "running" | "awaiting-decision" | "done" | "error";

export default function ClaimRunCard({
  claim,
  order,
  enabled,
  onDone,
  onActivity,
}: {
  claim: ScenarioClaim;
  order: number;
  enabled: boolean;
  onDone?: () => void;
  onActivity?: () => void;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [rows, setRows] = useState<TimelineRow[]>([]);
  const [pendingInterrupt, setPendingInterrupt] = useState<InterruptData | null>(null);
  const [finalEntry, setFinalEntry] = useState<LogEntry | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const settledRef = useRef(false);
  const idCounterRef = useRef(0);

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
    return () => closeSocket();
  }, [closeSocket]);

  const start = useCallback(async () => {
    setStatus("connecting");
    setErrorMessage(null);
    setFinalEntry(null);
    setPendingInterrupt(null);
    setRows([]);
    settledRef.current = false;
    idCounterRef.current = 0;

    try {
      const fields: ClaimFields = {
        plant: claim.plant,
        supplier: claim.supplier,
        lot_id: claim.lot_id,
        sku: claim.sku,
        quantity_needed: claim.quantity_needed,
        commitment_tier: claim.commitment_tier,
        days_of_cover: claim.days_of_cover,
        requested_at: claim.requested_at,
        requested_at_display: claim.requested_at_display,
      };
      const { thread_id } = await submitClaim(fields);
      const ws = new WebSocket(getClaimWsUrl(thread_id));
      wsRef.current = ws;

      ws.onopen = () => setStatus("running");

      ws.onmessage = (event: MessageEvent<string>) => {
        let message: ServerMessage;
        try {
          message = JSON.parse(event.data) as ServerMessage;
        } catch {
          return;
        }

        switch (message.type) {
          case "submit_claim":
            setRows((prev) => [...prev, { kind: "submit_claim", id: nextId("sc"), data: message.data }]);
            break;
          case "check_registry":
            setRows((prev) => [...prev, { kind: "check_registry", id: nextId("cr"), data: message.data }]);
            onActivity?.();
            break;
          case "grant":
            setRows((prev) => [...prev, { kind: "grant", id: nextId("gr"), data: message.data }]);
            onActivity?.();
            break;
          case "arbitrate":
            setRows((prev) => [...prev, { kind: "arbitrate", id: nextId("ar"), data: message.data }]);
            break;
          case "grant_winner":
            setRows((prev) => [...prev, { kind: "grant_winner", id: nextId("gw"), data: message.data }]);
            onActivity?.();
            break;
          case "suggest_alternate_for_loser":
            setRows((prev) => [
              ...prev,
              { kind: "suggest_alternate_for_loser", id: nextId("alt"), data: message.data },
            ]);
            break;
          case "escalate_to_kavitas_team":
            // The human decision row was already appended optimistically in
            // resolveInterrupt(); this message just confirms the graph
            // resumed with it. Nothing further to render here.
            break;
          case "log":
            setRows((prev) => [...prev, { kind: "log", id: nextId("lg"), data: message.data }]);
            break;
          case "interrupt":
            setPendingInterrupt(message.data);
            setStatus("awaiting-decision");
            break;
          case "done":
            settledRef.current = true;
            setFinalEntry(message.data.log[message.data.log.length - 1] ?? null);
            setStatus("done");
            onActivity?.();
            onDone?.();
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
        setErrorMessage("Connection to the backend closed unexpectedly before the claim finished.");
        setStatus("error");
      };
    } catch (err) {
      settledRef.current = true;
      setErrorMessage(err instanceof Error ? err.message : "Failed to submit the claim.");
      setStatus("error");
    }
  }, [claim, onActivity, onDone]);

  const resolveInterrupt = useCallback(
    (winnerPlant: string, decidedBy: string, note: string) => {
      const ws = wsRef.current;
      const interruptData = pendingInterrupt;
      if (!ws || !interruptData) return;

      const decision: ResumeMessage = { type: "resume", winner_plant: winnerPlant, decided_by: decidedBy, note };

      setRows((prev) => [
        ...prev,
        { kind: "escalation-resolved", id: nextId("esc"), data: interruptData, decision },
      ]);
      setPendingInterrupt(null);
      setStatus("running");

      try {
        ws.send(JSON.stringify(decision));
      } catch {
        settledRef.current = true;
        setErrorMessage("Failed to send the escalation decision to the backend.");
        setStatus("error");
      }
    },
    [pendingInterrupt]
  );

  const isBusy = status === "connecting" || status === "running" || status === "awaiting-decision";
  const canSubmit = enabled && (status === "idle" || status === "done" || status === "error");

  return (
    <section className="rounded-lg border border-border bg-panel p-4 sm:p-5 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="font-mono text-base text-soft">claim {order}</p>
          <h3 className="font-semibold">{claim.label}</h3>
          <p className="font-mono text-base text-soft mt-0.5">
            {claim.plant} · {claim.supplier} · lot {claim.lot_id} · qty {claim.quantity_needed} · tier{" "}
            {claim.commitment_tier ?? "n/a"} · {claim.days_of_cover ?? "n/a"}d cover · {claim.requested_at_display}
          </p>
        </div>
        <button
          type="button"
          onClick={start}
          disabled={!canSubmit}
          className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {status === "idle" && (enabled ? `Submit ${claim.plant}'s claim` : "Waiting for prior claim…")}
          {status === "connecting" && "Connecting…"}
          {status === "running" && "Running…"}
          {status === "awaiting-decision" && "Awaiting decision…"}
          {(status === "done" || status === "error") && "Resubmit"}
        </button>
      </div>

      {!enabled && status === "idle" && (
        <p className="text-base text-soft font-mono">
          Submit the claim above first, so this one actually collides against an open hold instead of a clean
          registry.
        </p>
      )}

      {status === "error" && errorMessage && (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-base text-danger">
          <span className="font-semibold">Stopped: </span>
          {errorMessage}
        </div>
      )}

      {pendingInterrupt && <PendingApprovalCard data={pendingInterrupt} onResolve={resolveInterrupt} />}

      {status === "done" && finalEntry && (
        <div
          className={`rounded-lg border p-3 space-y-1 ${
            finalEntry.type === "clear" ? "border-safe/40 bg-safe/10" : "border-accent/40 bg-accent/10"
          }`}
        >
          <p className={`font-semibold ${finalEntry.type === "clear" ? "text-safe" : "text-accent"}`}>
            {finalEntry.outcome.result === "granted" ? "Granted immediately" : "Granted after arbitration"}
          </p>
          <p className="text-base font-mono text-ink">{finalEntry.outcome.reason}</p>
          {finalEntry.escalated_to_human && (
            <p className="text-base font-mono text-danger">resolved by a human escalation, not the rulebook alone</p>
          )}
        </div>
      )}

      <div className="rounded-lg border border-border bg-bg/40 p-3">
        <Timeline rows={rows} />
      </div>
    </section>
  );
}
