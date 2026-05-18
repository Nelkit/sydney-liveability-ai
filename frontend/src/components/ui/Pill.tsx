type Props = {
  tone: "pos" | "neg";
  label: string;
  body: string;
  sub?: string;
};

const COLORS = {
  pos: {
    bg: "oklch(0.96 0.04 145)",
    bd: "oklch(0.85 0.06 145)",
    fg: "oklch(0.40 0.14 145)",
  },
  neg: {
    bg: "oklch(0.96 0.04 25)",
    bd: "oklch(0.85 0.06 25)",
    fg: "oklch(0.45 0.14 25)",
  },
};

export function Pill({ tone, label, body, sub }: Props) {
  const c = COLORS[tone];
  return (
    <div
      className="rounded-lg p-[10px]"
      style={{ background: c.bg, border: `1px solid ${c.bd}` }}
    >
      <div
        className="font-mono text-[9.5px] font-semibold uppercase tracking-[0.08em]"
        style={{ color: c.fg }}
      >
        {label}
      </div>
      <div className="mt-0.5 break-words text-sm font-semibold">{body}</div>
      {sub && <div className="mt-px font-mono text-[10.5px] text-fg-muted">{sub}</div>}
    </div>
  );
}
