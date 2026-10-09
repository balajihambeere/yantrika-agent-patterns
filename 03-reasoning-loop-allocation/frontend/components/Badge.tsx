type BadgeTone = "safe" | "accent" | "danger" | "soft";

const TONE_STYLES: Record<BadgeTone, string> = {
  safe: "bg-safe/15 text-safe border-safe/40",
  accent: "bg-accent/15 text-accent border-accent/40",
  danger: "bg-danger/15 text-danger border-danger/40",
  soft: "bg-soft/10 text-soft border-border",
};

export default function Badge({
  tone,
  children,
}: {
  tone: BadgeTone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-base font-mono uppercase tracking-wide whitespace-nowrap ${TONE_STYLES[tone]}`}
    >
      {children}
    </span>
  );
}
