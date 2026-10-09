import { fetchProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import type { Product } from "@/lib/types";

export default async function HomePage() {
  let products: Product[];
  let loadError: string | null = null;

  try {
    products = await fetchProducts();
  } catch {
    products = [];
    loadError =
      "Couldn't reach the backend at the configured NEXT_PUBLIC_API_URL. Make sure the FastAPI server is running on port 8000.";
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10">
      <div className="mb-8 space-y-2">
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
          Products
        </h1>
        <p className="text-soft max-w-2xl">
          Pick a wiring-harness SKU to start a live run. The agent will
          observe its stock events, decide what to do about them, and pause
          for your approval whenever a decision is high-risk.
        </p>
      </div>

      {loadError ? (
        <div className="rounded-lg border border-danger/40 bg-panel p-4 text-danger">
          {loadError}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
          {products.map((product) => (
            <ProductCard key={product.sku} product={product} />
          ))}
        </div>
      )}
    </div>
  );
}
