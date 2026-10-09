import { notFound } from "next/navigation";
import Image from "next/image";
import { fetchProduct, getApiUrl } from "@/lib/api";
import RunView from "@/components/RunView";
import ChatBox from "@/components/ChatBox";

export default async function ProductRunPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;

  let product;
  try {
    product = await fetchProduct(sku);
  } catch {
    product = null;
  }

  if (!product) {
    notFound();
  }

  const imageUrl = `${getApiUrl()}${product.image}`;

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <div className="flex items-center gap-4 sm:gap-6">
        <div className="relative h-20 w-20 sm:h-24 sm:w-24 shrink-0 rounded-lg overflow-hidden border border-border bg-panel">
          <Image src={imageUrl} alt={product.name} fill unoptimized className="object-cover" />
        </div>
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight truncate">
            {product.name}
          </h1>
          <p className="font-mono text-base text-accent">{product.sku}</p>
          <p className="font-mono text-base text-soft mt-1">
            opening balance {product.opening_balance} · run rate{" "}
            {product.run_rate_per_minute}/min · {product.event_count} events
          </p>
        </div>
      </div>

      <RunView sku={product.sku} />

      <ChatBox sku={product.sku} />
    </div>
  );
}
