import type { AspectScore } from "@/types/api";

type Props = {
  data: AspectScore[];
  accent?: string;
  size?: "sm" | "lg";
};

export function AspectRadar({ data, accent = "oklch(0.55 0.18 285)", size = "sm" }: Props) {
  const dim  = size === "lg" ? 320 : 240;
  const cx   = dim / 2;
  const cy   = dim / 2;
  const rMax = dim / 2 - (size === "lg" ? 36 : 30);
  const n    = data.length;

  const toNumber = (value: number | null | undefined) => (typeof value === "number" ? value : 0);
  const formatPos = (value: number | null | undefined) =>
    typeof value === "number" ? `${Math.round(value * 100)}%` : "n/a";

  const points = data.map((d, i) => {
    const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
    const r   = rMax * toNumber(d.pos);
    return { x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r, ang, label: d.aspect, v: toNumber(d.pos) };
  });

  const polyPath = points.map((p) => `${p.x},${p.y}`).join(" ");

  const dotColor = (v: number) =>
    v >= 0.6 ? "oklch(0.55 0.16 145)" : v >= 0.4 ? "oklch(0.65 0.02 250)" : "oklch(0.55 0.18 25)";

  return (
    <div className="flex flex-col items-center gap-3 md:flex-row md:items-center">
      <svg width={dim} height={dim}>
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <circle key={f} cx={cx} cy={cy} r={rMax * f} fill="none" stroke="oklch(0.92 0.005 250)" strokeWidth="0.6" />
        ))}
        {data.map((_, i) => {
          const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
          return <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(ang) * rMax} y2={cy + Math.sin(ang) * rMax} stroke="oklch(0.92 0.005 250)" strokeWidth="0.5" />;
        })}
        <polygon points={polyPath} fill={accent} fillOpacity="0.15" stroke={accent} strokeWidth="1.5" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={size === "lg" ? 3 : 2.5}
            fill={size === "lg" ? dotColor(p.v) : accent} />
        ))}
        {data.map((d, i) => {
          const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
          const r   = rMax + (size === "lg" ? 18 : 14);
          const x   = cx + Math.cos(ang) * r;
          const y   = cy + Math.sin(ang) * r;
          const anchor = Math.cos(ang) > 0.3 ? "start" : Math.cos(ang) < -0.3 ? "end" : "middle";
          return (
            <g key={i}>
              <text x={x} y={size === "lg" ? y - 5 : y} fontFamily="var(--font-mono)" fontSize={size === "lg" ? "11" : "9.5"}
                fontWeight={size === "lg" ? "500" : "400"}
                fill="oklch(0.55 0.012 250)" textAnchor={anchor} dominantBaseline="middle">
                {d.aspect}
              </text>
              {size === "lg" && (
                <text x={x} y={y + 7} fontFamily="var(--font-mono)" fontSize="9.5"
                  fill="oklch(0.55 0.012 250)" textAnchor={anchor} dominantBaseline="middle">
                  {formatPos(d.pos)} · {d.mentions}
                </text>
              )}
            </g>
          );
        })}
        {size === "lg" && (
          <text x={cx} y={cy + 4} fontFamily="var(--font-mono)" fontSize="10" fill="oklch(0.55 0.012 250)" textAnchor="middle">
            LIVEABILITY
          </text>
        )}
      </svg>

      <div className="flex w-full flex-col gap-1.5 md:flex-1">
        {size === "lg" && (
          <>
            <div className="flex gap-3 font-mono text-[10px] text-fg-muted">
              {[
                { color: "oklch(0.55 0.16 145)", label: "positive" },
                { color: "oklch(0.65 0.02 250)", label: "neutral"  },
                { color: "oklch(0.55 0.18 25)",  label: "negative" },
              ].map(({ color, label }) => (
                <span key={label} className="flex items-center gap-1">
                  <span className="size-2 rounded-full" style={{ background: color }} />
                  {label}
                </span>
              ))}
            </div>
            <div className="my-1 h-px bg-border" />
          </>
        )}
        {[...data]
          .sort((a, b) => toNumber(b.pos) - toNumber(a.pos))
          .slice(0, size === "lg" ? 6 : 4)
          .map((d) => (
          <div key={d.aspect} className="flex flex-col gap-[3px]">
            <div className="flex justify-between text-[11px]">
              <span className="text-fg">{d.aspect}</span>
              <span className="font-mono text-fg-muted">{formatPos(d.pos)}{size === "sm" && ` · ${d.mentions}`}</span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-border">
              <div className="h-full rounded-full" style={{ width: `${toNumber(d.pos) * 100}%`, background: size === "lg" ? dotColor(toNumber(d.pos)) : accent }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function dotColor(v: number) {
  return v >= 0.6 ? "oklch(0.55 0.16 145)" : v >= 0.4 ? "oklch(0.65 0.02 250)" : "oklch(0.55 0.18 25)";
}
