"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createRun, getWsUrl } from "@/lib/api";
import type { InterruptData, LogEntry, ResumeMessage, ServerMessage, TimelineRow } from "@/lib/types";
import Timeline from "./Timeline";
import PendingApprovalCard from "./PendingApprovalCard";

type Status = "idle" | "connecting" | "running" | "awaiting-approval" | "done" | "error";

type DoneSummary = {
  totalEntries: number;
  approvalsRequired: number;
  approvalsApproved: number;
};

function summarize(log: LogEntry[]): DoneSummary {
  const approvalEntries = log.filter((entry) => entry.decision.requires_human);
  return {
    totalEntries: log.length,
    approvalsRequired: approvalEntries.length,
    approvalsApproved: approvalEntries.filter((entry) => entry.decision.approved).length,
  };
}

export default function RunView({ sku }: { sku: string }) {
  const [status, setStatus] = useState<Status>("idle");
  const [rows, setRows] = useState<TimelineRow[]>([]);
  const [pendingInterrupt, setPendingInterrupt] = useState<InterruptData | null>(null);
  const [doneSummary, setDoneSummary] = useState<DoneSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const settledRef = useRef(false);
  const idCounterRef = useRef(0);
  // Synchronous re-entrancy guard. React state (`status`) only updates the
  // DOM's `disabled` attribute after a render, which isn't fast enough to
  // stop a second click (e.g. a retry click fired before the first render
  // lands) from starting a second concurrent run — two open WebSockets
  // would then both feed events into this same component's state, making
  // the run look like it never converges. This ref is set synchronously,
  // the instant startRun() begins, so a second call bails out immediately
  // regardless of render timing.
  const startingRef = useRef(false);

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
    if (startingRef.current) return; // a run is already starting/active — ignore the extra click
    startingRef.current = true;

    closeSocket(); // defensively close any stale socket before opening a new one

    setStatus("connecting");
    setErrorMessage(null);
    setDoneSummary(null);
    setPendingInterrupt(null);
    setRows([]);
    settledRef.current = false;
    idCounterRef.current = 0;

    try {
      const { thread_id } = await createRun(sku);
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
          case "observe":
            setRows((prev) => [...prev, { kind: "observe", id: nextId("obs"), data: message.data }]);
            break;
          case "decide":
            setRows((prev) => [...prev, { kind: "decide", id: nextId("dec"), data: message.data }]);
            break;
          case "act":
            setRows((prev) => [...prev, { kind: "act", id: nextId("act"), data: message.data }]);
            break;
          case "interrupt":
            setPendingInterrupt(message.data);
            setStatus("awaiting-approval");
            break;
          case "done":
            settledRef.current = true;
            startingRef.current = false;
            setDoneSummary(summarize(message.data.log));
            setStatus("done");
            break;
          case "error":
            settledRef.current = true;
            startingRef.current = false;
            setErrorMessage(message.data.message);
            setStatus("error");
            break;
        }
      };

      ws.onerror = () => {
        if (settledRef.current) return;
        settledRef.current = true;
        startingRef.current = false;
        setErrorMessage("WebSocket connection error.");
        setStatus("error");
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (settledRef.current) return;
        settledRef.current = true;
        startingRef.current = false;
        setErrorMessage("Connection to the backend closed unexpectedly before the run finished.");
        setStatus("error");
      };
    } catch (err) {
      settledRef.current = true;
      startingRef.current = false;
      setErrorMessage(err instanceof Error ? err.message : "Failed to start the run.");
      setStatus("error");
    }
  }, [sku, closeSocket]);

  const resolveInterrupt = useCallback(
    (approved: boolean, approvedBy: string | null) => {
      const ws = wsRef.current;
      const interruptData = pendingInterrupt;
      if (!ws || !interruptData) return;

      setRows((prev) => [
        ...prev,
        {
          kind: "interrupt-resolved",
          id: nextId("int"),
          data: interruptData,
          approved,
          approvedBy,
        },
      ]);
      setPendingInterrupt(null);
      setStatus("running");

      const reply: ResumeMessage = { type: "resume", approved, approved_by: approvedBy };
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
          {status === "awaiting-approval" && "Awaiting approval…"}
          {(status === "done" || status === "error") && "Run Again"}
        </button>
      </div>

      {status === "error" && errorMessage && (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-base text-danger">
          <span className="font-semibold">Run stopped: </span>
          {errorMessage}
        </div>
      )}

      {pendingInterrupt && (
        <PendingApprovalCard data={pendingInterrupt} onResolve={resolveInterrupt} />
      )}

      {status === "done" && doneSummary && (
        <div className="rounded-lg border border-safe/40 bg-safe/10 p-4 space-y-1">
          <p className="font-semibold text-safe">Run complete</p>
          <p className="text-base font-mono text-ink">
            {doneSummary.totalEntries} log entries · {doneSummary.approvalsRequired} required human
            approval
            {doneSummary.approvalsRequired !== 1 ? "s" : ""}
            {doneSummary.approvalsRequired > 0 &&
              ` (${doneSummary.approvalsApproved} approved, ${
                doneSummary.approvalsRequired - doneSummary.approvalsApproved
              } declined)`}
          </p>
        </div>
      )}

      <div className="rounded-lg border border-border bg-bg/40 p-3 sm:p-4">
        <Timeline rows={rows} />
      </div>
    </section>
  );
}
