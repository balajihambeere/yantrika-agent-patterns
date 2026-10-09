import Image from "next/image";
import Link from "next/link";
import type { Scenario } from "@/lib/types";
import { getApiUrl } from "@/lib/api";
import CollisionBadge from "./CollisionBadge";

export default function ScenarioCard({ scenario }: { scenario: Scenario }) {
  return (
    <Link
      href={`/runs/${scenario.id}`}
      className="group block rounded-lg border border-border bg-panel overflow-hidden hover:border-accent transition-colors p-5 space-y-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          {scenario.image && (
            <div className="relative h-12 w-12 shrink-0 rounded-md bg-bg overflow-hidden">
              {/* Backend-served image; remote host varies by env, so skip
                  next/image optimization rather than configure every
                  possible NEXT_PUBLIC_API_URL host. */}
              <Image
                src={`${getApiUrl()}${scenario.image}`}
                alt={scenario.sku_family}
                fill
                unoptimized
                sizes="48px"
                className="object-contain p-1.5"
              />
            </div>
          )}
          <h2 className="font-semibold leading-snug group-hover:text-accent transition-colors">
            {scenario.title}
          </h2>
        </div>
        <CollisionBadge collision={scenario.expect_collision} />
      </div>
      <p className="text-base text-soft leading-relaxed">{scenario.description}</p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-base font-mono text-soft pt-2 border-t border-border">
        <dt className="col-span-1 pt-2">{scenario.pune_position.site}</dt>
        <dd className="col-span-1 pt-2 text-right text-ink">
          {scenario.pune_position.on_hand} on hand / {scenario.pune_position.buffer_target} target
        </dd>
        <dt className="col-span-1">{scenario.nashik_position.site}</dt>
        <dd className="col-span-1 text-right text-ink">
          {scenario.nashik_position.on_hand} on hand / {scenario.nashik_position.buffer_target} target
        </dd>
        <dt className="col-span-1">supplier</dt>
        <dd className="col-span-1 text-right text-ink">{scenario.supplier}</dd>
        <dt className="col-span-1">connection tier</dt>
        <dd className="col-span-1 text-right text-ink">{scenario.connection_tier}</dd>
      </dl>
    </Link>
  );
}
