"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRegistry } from "@/lib/api";
import type { RegistryHoldStatus, RegistrySnapshot } from "@/lib/types";

const STATUS_STYLES: Record<RegistryHoldStatus, string> = {
  pending: "text-accent",
  confirmed: "text-safe",
  closed_lost: "text-danger",
};

export default function RegistryPanel({ refreshToken }: { refreshToken?: number }) {
  const [snapshot, setSnapshot] = useState<RegistrySnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchRegistry();
      if (mountedRef.current) {
        setSnapshot(data);
        setError(null);
      }
    } catch {
      if (mountedRef.current) setError("Couldn't reach /api/registry.");
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    const interval = setInterval(() => void refresh(), 3000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [refresh]);

  // An external activity signal (a claim's run reaching a registry-changing
  // node) triggers an immediate refresh instead of waiting for the next poll.
  useEffect(() => {
    if (refreshToken !== undefined) void refresh();
  }, [refreshToken, refresh]);

  const lots = snapshot ? Object.entries(snapshot.holds) : [];

  return (
    <aside className="rounded-lg border border-border bg-panel p-4 space-y-3 sticky top-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-base text-soft uppercase tracking-wide">Lot Registry — live</h2>
        <span aria-hidden className="inline-block h-2 w-2 rounded-full bg-safe animate-pulse" />
      </div>

      {error && <p className="text-base text-danger">{error}</p>}

      {lots.length === 0 ? (
        <p className="text-base text-soft font-mono">No open holds yet — submit a claim to see it appear here.</p>
      ) : (
        <div className="space-y-4">
          {lots.map(([lotKey, holds]) => (
            <div key={lotKey} className="space-y-1.5">
              <p className="font-mono text-base text-ink break-words">{lotKey}</p>
              <ul className="space-y-1.5 pl-2">
                {holds.map((h, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 text-base font-mono">
                    <span className="text-soft break-words">{h.plant}</span>
                    <span className={`shrink-0 ${STATUS_STYLES[h.status]}`}>{h.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <div className="pt-2 border-t border-border">
        <p className="text-base font-mono text-soft">
          audit log entries: {snapshot?.audit_log.length ?? 0}
        </p>
      </div>
    </aside>
  );
}
