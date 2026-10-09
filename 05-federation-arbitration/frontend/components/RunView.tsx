"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createRun, getWsUrl } from "@/lib/api";
import type {
  CollisionReport,
  Decision,
  InterruptData,
  LocalRecommendation,
  LogEntry,
  ResumeMessage,
  ServerMessage,
  TimelineRow,
} from "@/lib/types";
import SenseBoard from "./SenseBoard";
import ArbitrateRow from "./ArbitrateRow";
import ApproverConfirmCard from "./ApproverConfirmCard";
import ConfirmationResolvedRow from "./ConfirmationResolvedRow";
import DecisionCard from "./DecisionCard";

type Status =
  | "idle"
  | "connecting"
  | "running"
  | "awaiting-neha"
  | "awaiting-shalini"
  | "done"
  | "error";

export default function RunView({ scenarioId }: { scenarioId: string }) {
  const [status, setStatus] = useState<Status>("idle");
  const [puneRec, setPuneRec] = useState<LocalRecommendation | null>(null);
  const [nashikRec, setNashikRec] = useState<LocalRecommendation | null>(null);
  const [collision, setCollision] = useState<CollisionReport | null | undefined>(undefined);
  const [resolvedRows, setResolvedRows] = useState<TimelineRow[]>([]);
  const [pendingInterrupt, setPendingInterrupt] = useState<InterruptData | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [doneLog, setDoneLog] = useState<LogEntry[] | null>(null);
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
    // Close the socket if the user navigates away mid-run.
    return () => closeSocket();
  }, [closeSocket]);

  const startRun = useCallback(async () => {
    setStatus("connecting");
    setErrorMessage(null);
    setPuneRec(null);
    setNashikRec(null);
    setCollision(undefined);
    setResolvedRows([]);
    setPendingInterrupt(null);
    setDecision(null);
    setDoneLog(null);
    settledRef.current = false;
    idCounterRef.current = 0;

    try {
      const { thread_id } = await createRun(scenarioId);
      const ws = new WebSocket(getWsUrl(thread_id));
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
          case "sense_pune":
            setPuneRec(message.data);
            break;
          case "sense_nashik":
            setNashikRec(message.data);
            break;
          case "arbitrate":
            setCollision(message.data.collision);
            break;
          case "interrupt":
            setPendingInterrupt(message.data);
            setStatus(message.data.approver_key === "neha" ? "awaiting-neha" : "awaiting-shalini");
            break;
          case "act":
            setDecision(message.data);
            break;
          case "log":
            // Full detail arrives again in "done" — nothing additional to
            // render here, the act/decision card already covers it.
            break;
          case "done":
            settledRef.current = true;
            setDoneLog(message.data.log);
            setStatus("done");
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
  }, [scenarioId]);

  const resolveInterrupt = useCallback(
    (confirmed: boolean, note: string) => {
      const ws = wsRef.current;
      const interrupt = pendingInterrupt;
      if (!ws || !interrupt) return;

      setResolvedRows((prev) => [
        ...prev,
        {
          kind: "confirmation-resolved",
          id: nextId("conf"),
          approverKey: interrupt.approver_key,
          interrupt,
          confirmed,
          confirmedBy: interrupt.confirmer,
          note,
        },
      ]);
      setPendingInterrupt(null);
      setStatus("running");

      const reply: ResumeMessage = {
        type: "resume",
        confirmed,
        confirmed_by: interrupt.confirmer,
        note,
      };
      try {
        ws.send(JSON.stringify(reply));
      } catch {
        settledRef.current = true;
        setErrorMessage("Failed to send the confirmation to the backend.");
        setStatus("error");
      }
    },
    [pendingInterrupt]
  );

  const isBusy =
    status === "connecting" ||
    status === "running" ||
    status === "awaiting-neha" ||
    status === "awaiting-shalini";

  const hasStarted = status !== "idle";

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="font-semibold text-lg">Run</h2>
        <button
          type="button"
          onClick={startRun}
          disabled={isBusy}
          className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {status === "idle" && "Start Run"}
          {status === "connecting" && "Connecting…"}
          {status === "running" && "Running…"}
          {status === "awaiting-neha" && "Awaiting Neha…"}
          {status === "awaiting-shalini" && "Awaiting Shalini…"}
          {(status === "done" || status === "error") && "Run Again"}
        </button>
      </div>

      {status === "error" && errorMessage && (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-base text-danger">
          <span className="font-semibold">Run stopped: </span>
          {errorMessage}
        </div>
      )}

      {!hasStarted && (
        <p className="text-base text-soft font-mono py-6 text-center rounded-lg border border-border bg-bg/40">
          No activity yet — start a run to watch Pune and Nashik sense in parallel.
        </p>
      )}

      {hasStarted && (
        <div className="space-y-3">
          <SenseBoard puneRec={puneRec} nashikRec={nashikRec} />

          {(collision !== undefined || puneRec || nashikRec) && (
            <div className="rounded-lg border border-border bg-bg/40 p-3 sm:p-4 space-y-2">
              <ArbitrateRow collision={collision} />

              {/* The sequential, named-human confirmation flow — only ever
                  rendered when there is something to confirm. Resolved
                  steps render first in the order they actually happened
                  (Neha's, then Shalini's); the live pending card for
                  whichever one hasn't answered yet renders below them.
                  Shalini's card is never shown at all if Neha declined,
                  because the backend never sends that interrupt. */}
              {resolvedRows.map((row) =>
                row.kind === "confirmation-resolved" ? (
                  <ConfirmationResolvedRow key={row.id} row={row} />
                ) : null
              )}

              {pendingInterrupt && (
                <ApproverConfirmCard interrupt={pendingInterrupt} onResolve={resolveInterrupt} />
              )}

              {decision && <DecisionCard decision={decision} />}
            </div>
          )}

          {status === "done" && doneLog && (
            <div className="rounded-lg border border-safe/40 bg-safe/10 p-4 space-y-1">
              <p className="font-semibold text-safe">Run complete</p>
              <p className="text-base font-mono text-ink">
                {doneLog.length} log entry — decision: {doneLog[doneLog.length - 1].decision.type}
                {doneLog[doneLog.length - 1].collision
                  ? " · collision caught before it executed"
                  : " · no collision, each site acted independently"}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
