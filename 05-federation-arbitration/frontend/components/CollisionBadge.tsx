export default function CollisionBadge({ collision }: { collision: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-base font-mono uppercase tracking-wide ${
        collision ? "bg-danger/15 text-danger border-danger/40" : "bg-safe/15 text-safe border-safe/40"
      }`}
    >
      {collision ? "collision detected" : "no collision"}
    </span>
  );
}
