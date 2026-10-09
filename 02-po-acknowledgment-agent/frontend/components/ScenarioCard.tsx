import Image from "next/image";
import Link from "next/link";
import type { Scenario } from "@/lib/types";
import { getApiUrl } from "@/lib/api";

export default function ScenarioCard({ scenario }: { scenario: Scenario }) {
  return (
    <Link
      href={`/scenarios/${scenario.id}`}
      className="group block rounded-lg border border-border bg-panel overflow-hidden hover:border-accent transition-colors"
    >
      {scenario.image && (
        <div className="relative aspect-square bg-bg">
          {/* Backend-served image; remote host varies by env, so skip
              next/image optimization rather than configure every possible
              NEXT_PUBLIC_API_URL host. */}
          <Image
            src={`${getApiUrl()}${scenario.image}`}
            alt={scenario.supplier}
            fill
            unoptimized
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
            className="object-contain p-6 group-hover:scale-[1.02] transition-transform"
          />
        </div>
      )}
      <div className="p-4 sm:p-5 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <h2 className="font-semibold leading-snug group-hover:text-accent transition-colors">
            {scenario.supplier}
          </h2>
        </div>
        <p className="font-mono text-base text-accent">{scenario.po_number}</p>
        <p className="text-base text-soft leading-snug">{scenario.summary}</p>
        <dl className="grid grid-cols-3 gap-x-3 gap-y-1.5 text-base font-mono text-soft pt-2 border-t border-border">
          <dt className="col-span-1 pt-2">qty</dt>
          <dt className="col-span-1 pt-2">ordered</dt>
          <dt className="col-span-1 pt-2">hrs since PO</dt>
          <dd className="col-span-1 text-ink">{scenario.ordered_qty}</dd>
          <dd className="col-span-1 text-ink">{scenario.ordered_date}</dd>
          <dd className="col-span-1 text-ink">{scenario.hours_since_po}</dd>
        </dl>
      </div>
    </Link>
  );
}
