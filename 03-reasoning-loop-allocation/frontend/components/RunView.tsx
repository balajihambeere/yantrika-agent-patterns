"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createRun, getWsUrl } from "@/lib/api";
import type { InterruptData, LogEntryData, ResumeMessage, ServerMessage, TimelineRow } from "@/lib/types";
import Timeline from "./Timeline";
import PendingApprovalCard from "./PendingApprovalCard";

type Status = "idle" | "connecting" | "running" | "awaiting-approval" | "done" | "error";

type DoneSummary = {
  cyclesRun: number;
  escalations: number;
  overrides: number;
};

function summarize(log: LogEntryData[]): DoneSummary {
  return {
    cyclesRun: log.length,
    escalations: log.filter((entry) => entry.requires_human).length,
    overrides: log.filter((entry) => entry.decision.overridden).length,
  };
}

export default function RunView({ scenarioId }: { scenarioId: string }) {
  const [status, setStatus] = useState<Status>("idle");
  const [rows, setRows] = useState<TimelineRow[]>([]);
  const [pendingInterrupt, setPendingInterrupt] = useState<InterruptData | null>(null);
  const [doneSummary, setDoneSummary] = useState<DoneSummary | null>(null);
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
    setDoneSummary(null);
    setPendingInterrupt(null);
    setRows([]);
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
          case "sense":
            setRows((prev) => [...prev, { kind: "sense", id: nextId("sense"), data: message.data }]);
            break;
          case "weigh":
            setRows((prev) => [...prev, { kind: "weigh", id: nextId("weigh"), data: message.data }]);
            break;
          case "recommend":
            setRows((prev) => [...prev, { kind: "recommend", id: nextId("rec"), data: message.data }]);
            break;
          case "act":
            setRows((prev) => [...prev, { kind: "act", id: nextId("act"), data: message.data }]);
            break;
          case "log":
            setRows((prev) => [...prev, { kind: "log", id: nextId("log"), data: message.data }]);
            break;
          case "interrupt":
            setPendingInterrupt(message.data);
            setStatus("awaiting-approval");
            break;
          case "done":
            settledRef.current = true;
            setDoneSummary(summarize(message.data.log));
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
    (resolution: ResumeMessage) => {
      const ws = wsRef.current;
      const interruptData = pendingInterrupt;
      if (!ws || !interruptData) return;

      setRows((prev) => [
        ...prev,
        {
          kind: "escalate-resolved",
          id: nextId("esc"),
          data: interruptData,
          resolution,
        },
      ]);
      setPendingInterrupt(null);
      setStatus("running");

      try {
        ws.send(JSON.stringify(resolution));
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
          {status === "awaiting-approval" && "Awaiting decision…"}
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
            {doneSummary.cyclesRun} sensing cycle{doneSummary.cyclesRun !== 1 ? "s" : ""} logged ·{" "}
            {doneSummary.escalations} escalated to a human
            {doneSummary.overrides > 0 && ` (${doneSummary.overrides} overridden)`}
          </p>
        </div>
      )}

      <div className="rounded-lg border border-border bg-bg/40 p-3 sm:p-4">
        <Timeline rows={rows} />
      </div>
    </section>
  );
}
