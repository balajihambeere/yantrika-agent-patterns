import type { TimelineRow } from "@/lib/types";

export default function ConfirmationResolvedRow({
  row,
}: {
  row: Extract<TimelineRow, { kind: "confirmation-resolved" }>;
}) {
  const siteTag = row.approverKey === "neha" ? "PUNE" : "NASHIK";
  return (
    <div className="flex gap-3">
      <div className="pt-1 shrink-0 w-28 text-right">
        <span className="text-base font-mono text-soft uppercase">{siteTag}</span>
      </div>
      <div
        className={`flex-1 rounded-md border px-3 py-2.5 ${
          row.confirmed ? "border-safe/40 bg-safe/10" : "border-danger/40 bg-danger/10"
        }`}
      >
        <div className="flex items-center gap-2 text-base font-mono flex-wrap">
          <span className="uppercase tracking-wide text-soft">{row.interrupt.role}</span>
          <span className="text-ink font-semibold">{row.interrupt.confirmer}</span>
          <span className={row.confirmed ? "text-safe" : "text-danger"}>
            {row.confirmed ? "confirmed" : "declined"}
          </span>
        </div>
        <p className="text-base text-soft mt-0.5">{row.interrupt.proposed_action}</p>
        {row.note && <p className="text-base text-ink font-mono mt-1">&ldquo;{row.note}&rdquo;</p>}
      </div>
    </div>
  );
}
