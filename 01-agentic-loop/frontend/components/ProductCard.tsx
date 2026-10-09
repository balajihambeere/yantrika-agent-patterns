import Image from "next/image";
import Link from "next/link";
import type { Product } from "@/lib/types";
import { getApiUrl } from "@/lib/api";

export default function ProductCard({ product }: { product: Product }) {
  const imageUrl = `${getApiUrl()}${product.image}`;

  return (
    <Link
      href={`/products/${product.sku}`}
      className="group block rounded-lg border border-border bg-panel overflow-hidden hover:border-accent transition-colors"
    >
      <div className="relative aspect-square bg-bg">
        {/* Backend-served product renders; remote host varies by env, so
            skip next/image optimization rather than configure every possible
            NEXT_PUBLIC_API_URL host. */}
        <Image
          src={imageUrl}
          alt={product.name}
          fill
          unoptimized
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
          className="object-cover group-hover:scale-[1.02] transition-transform"
        />
      </div>
      <div className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h2 className="font-semibold leading-snug">{product.name}</h2>
        </div>
        <p className="font-mono text-base text-accent">{product.sku}</p>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-base font-mono text-soft pt-1">
          <dt className="col-span-1">opening bal.</dt>
          <dd className="col-span-1 text-right text-ink">{product.opening_balance}</dd>
          <dt className="col-span-1">run rate/min</dt>
          <dd className="col-span-1 text-right text-ink">{product.run_rate_per_minute}</dd>
          <dt className="col-span-1">events</dt>
          <dd className="col-span-1 text-right text-ink">{product.event_count}</dd>
        </dl>
      </div>
    </Link>
  );
}
