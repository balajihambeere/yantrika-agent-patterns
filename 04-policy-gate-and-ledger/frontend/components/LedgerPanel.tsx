"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { fetchLedger } from "@/lib/api";
import type { LedgerListResponse } from "@/lib/types";

// The signature feature of this example: a live, growing audit trail
// read straight from the shared DecisionLedger. Seeded server-side with
// `initialData` (so the record list is present in the first HTML response,
// not only after client JS hydrates) and then polls so it keeps picking up
// every run completed anywhere — this tab, another tab, another run on
// the page — without the viewer having to do anything.
export default function LedgerPanel({ initialData }: { initialData: LedgerListResponse | null }) {
  const [data, setData] = useState<LedgerListResponse | null>(initialData);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetchLedger(25);
      setData(res);
      setError(null);
    } catch {
      setError("Couldn't reach the backend.");
    }
  }, []);

  useEffect(() => {
    // Deliberate mount-time data fetch + poll, not derived render state —
    // `load`'s setState calls land after its own `await`, never synchronously
    // during this effect's commit.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <section className="rounded-lg border border-border bg-panel p-4 sm:p-5 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="font-semibold text-lg">Decision Ledger</h2>
        <div className="flex items-center gap-3 text-base font-mono text-soft">
          {data && (
            <>
              <span>
                {data.total_records} record{data.total_records === 1 ? "" : "s"}
              </span>
              <span className={data.chain_intact ? "text-safe" : "text-danger"}>
                chain {data.chain_intact ? "intact" : `BROKEN at ${data.chain_broken_at}`}
              </span>
            </>
          )}
          <button
            type="button"
            onClick={load}
            className="rounded-md border border-border px-2 py-1 hover:border-accent hover:text-accent transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && <p className="text-base text-danger">{error}</p>}

      {data && data.records.length === 0 && (
        <p className="text-base text-soft font-mono py-6 text-center">
          No decisions logged yet — start a request above to write the first five-part record.
        </p>
      )}

      <div className="space-y-3 max-h-[34rem] overflow-y-auto pr-1">
        {data?.records.map((record) => (
          <Link
            key={record.decision_id}
            href={`/ledger/${record.decision_id}`}
            className="block rounded-md border border-border px-3 py-3 hover:border-accent transition-colors"
          >
            <div className="flex items-center justify-between gap-2 flex-wrap text-base font-mono text-soft">
              <span className="text-ink font-semibold">{record.decision_id}</span>
              <span>{record.agent_id}</span>
              <span className="uppercase tracking-wide">{record.record_type}</span>
              <span>tier {record.tier}</span>
              <span>{record.policy_version}</span>
            </div>
            <p className="text-base text-ink mt-1.5">
              {record.outcome
                ? String((record.outcome as Record<string, unknown>).result ?? JSON.stringify(record.outcome))
                : "(outcome not yet known)"}
            </p>
            <p className="text-base text-soft mt-1">{record.timestamp}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
