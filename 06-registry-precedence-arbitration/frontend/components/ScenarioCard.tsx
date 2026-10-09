import Image from "next/image";
import Link from "next/link";
import type { Scenario } from "@/lib/types";
import { getApiUrl } from "@/lib/api";
import OutcomeBadge from "./OutcomeBadge";

export default function ScenarioCard({ scenario, image }: { scenario: Scenario; image: string | null }) {
  return (
    <Link
      href={`/scenarios/${scenario.id}`}
      className="group block rounded-lg border border-border bg-panel overflow-hidden hover:border-accent transition-colors p-4 sm:p-5 space-y-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          {image && (
            <div className="relative h-12 w-12 shrink-0 rounded-md bg-bg overflow-hidden">
              {/* Backend-served image; remote host varies by env, so skip
                  next/image optimization rather than configure every
                  possible NEXT_PUBLIC_API_URL host. */}
              <Image
                src={`${getApiUrl()}${image}`}
                alt="Lot bolt SKU"
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
        <OutcomeBadge outcome={scenario.expected_outcome} />
      </div>
      <p className="text-base text-soft">{scenario.summary}</p>
      <p className="font-mono text-base text-accent">
        {scenario.claim_count === 1
          ? "1 claim to submit"
          : `${scenario.claim_count} claims to submit, in order`}
      </p>
    </Link>
  );
}
