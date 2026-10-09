import type { CollisionReport } from "@/lib/types";
import CollisionBadge from "./CollisionBadge";

export default function ArbitrateRow({ collision }: { collision: CollisionReport | null | undefined }) {
  return (
    <div className="flex gap-3">
      <div className="pt-1 shrink-0 w-28 text-right">
        <span aria-hidden className="inline-block h-2 w-2 rounded-full bg-soft" />
      </div>
      <div className="flex-1 rounded-md border border-border bg-panel px-3 py-2.5">
        <div className="flex items-center gap-2 text-base font-mono text-soft flex-wrap">
          <span className="uppercase tracking-wide">arbitrate</span>
          {collision !== undefined && <CollisionBadge collision={collision !== null} />}
        </div>
        {collision === undefined ? (
          <p className="text-base text-soft font-mono mt-0.5">waiting for both sites to finish sensing…</p>
        ) : collision === null ? (
          <p className="text-base text-soft mt-0.5">
            The two recommendations don&apos;t touch the same resource — no arbitration needed.
          </p>
        ) : (
          <p className="text-base text-ink mt-0.5">{collision.description}</p>
        )}
      </div>
    </div>
  );
}
