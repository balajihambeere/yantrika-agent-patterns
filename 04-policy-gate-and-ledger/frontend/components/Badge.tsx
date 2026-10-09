const VARIANT_STYLES = {
  safe: "bg-safe/15 text-safe border-safe/40",
  danger: "bg-danger/15 text-danger border-danger/40",
  accent: "bg-accent/15 text-accent border-accent/40",
  soft: "bg-bg text-soft border-border",
} as const;

export default function Badge({
  children,
  variant = "soft",
}: {
  children: React.ReactNode;
  variant?: keyof typeof VARIANT_STYLES;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-base font-mono uppercase tracking-wide ${VARIANT_STYLES[variant]}`}
    >
      {children}
    </span>
  );
}
