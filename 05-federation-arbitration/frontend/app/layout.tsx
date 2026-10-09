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
  title: "Federation Arbitration — Two-Plant Rollout",
  description:
    "A LangGraph arbitration layer resolving a cross-plant collision between Pune's and Nashik's site agents, gated behind two separate named-human confirmations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col bg-bg text-ink">
        <header className="border-b border-border bg-panel">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-2 group">
              <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full bg-accent" />
              <span className="font-semibold tracking-tight text-lg group-hover:text-accent transition-colors">
                Federation Arbitration
              </span>
              <span className="hidden sm:inline font-mono text-base text-soft">
                Pune ⇄ Nashik
              </span>
            </Link>
            <Link
              href="/"
              className="font-mono text-base text-soft hover:text-accent transition-colors"
            >
              ← Scenarios
            </Link>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-border bg-panel">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-3 text-base font-mono text-soft">
            sense_pune ∥ sense_nashik → arbitrate → (confirm_neha → confirm_shalini) → act → log
          </div>
        </footer>
      </body>
    </html>
  );
}
