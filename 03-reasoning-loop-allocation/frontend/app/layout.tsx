import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Reasoning Loop — Harness Allocation",
  description:
    "A LangGraph continuous reasoning loop weighing competing claims on a constrained SKU, with a real human-in-the-loop pause whenever the bounded-autonomy threshold isn't clearly met.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col bg-bg text-ink">
        <header className="border-b border-border bg-panel">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-2 group">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 rounded-full bg-accent"
              />
              <span className="font-semibold tracking-tight text-lg group-hover:text-accent transition-colors">
                Reasoning Loop
              </span>
              <span className="hidden sm:inline font-mono text-base text-soft">
                harness allocation
              </span>
            </Link>
            <Link
              href="/"
              className="font-mono text-base sm:text-base text-soft hover:text-accent transition-colors"
            >
              ← Scenarios
            </Link>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-border bg-panel">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-3 text-base font-mono text-soft">
            Sense → Weigh → Recommend → (escalate) → Act → Log → back to Sense
          </div>
        </footer>
      </body>
    </html>
  );
}
