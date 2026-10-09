import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-16 text-center space-y-4">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="text-soft">
        That page, or that scenario, doesn&apos;t exist.
      </p>
      <Link href="/" className="inline-block font-mono text-accent hover:underline">
        ← back to scenarios
      </Link>
    </div>
  );
}
