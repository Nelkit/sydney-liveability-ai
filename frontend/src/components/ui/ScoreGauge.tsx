type Props = {
  value: number;
  size?: number;
  label?: string;
};

export function ScoreGauge({ value, size = 56, label }: Props) {
  const r   = size / 2 - 4;
  const c   = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value)) / 100;
  const numSize  = Math.round(size * 0.32);
  const lblSize  = 8;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="oklch(0.92 0.005 250)" strokeWidth={3}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="oklch(0.55 0.18 285)" strokeWidth={3}
          strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="font-mono font-semibold" style={{ fontSize: numSize }}>
          {value}
        </span>
        {label && (
          <span
            className="mt-0.5 font-mono uppercase tracking-[0.06em] text-fg-muted"
            style={{ fontSize: lblSize }}
          >
            {label}
          </span>
        )}
      </div>
    </div>
  );
}
