import type { RouterCategory } from "@/types/api";

const KIND_CONFIG: Record<RouterCategory, { label: string; hue: number; mute?: boolean }> = {
  crime:       { label: "crime",       hue: 25 },
  gis:         { label: "gis",         hue: 235 },
  sentiment:   { label: "sentiment",   hue: 75 },
  comparator:  { label: "comparator",  hue: 285 },
  out_of_scope:{ label: "out_of_scope",hue: 250, mute: true },
};

type Props = {
  kind: RouterCategory;
  active?: boolean;
  size?: "xs" | "sm";
};

export function CategoryChip({ kind, active = true, size = "sm" }: Props) {
  const c = KIND_CONFIG[kind] ?? { label: kind, hue: 250 };

  const bg    = c.mute ? `oklch(0.96 0.005 ${c.hue})` : `oklch(0.96 0.04 ${c.hue})`;
  const fg    = c.mute ? `oklch(0.55 0.01 ${c.hue})`  : `oklch(0.40 0.14 ${c.hue})`;
  const bd    = c.mute ? `oklch(0.90 0.005 ${c.hue})` : `oklch(0.85 0.05 ${c.hue})`;
  const dot   = c.mute ? `oklch(0.65 0.02 ${c.hue})`  : `oklch(0.55 0.16 ${c.hue})`;

  const padY  = size === "xs" ? "py-[2px]" : "py-[3px]";
  const padX  = size === "xs" ? "px-[6px]" : "px-[8px]";
  const fs    = size === "xs" ? "text-[10px]" : "text-[11px]";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-mono font-medium lowercase tracking-[0.02em] whitespace-nowrap ${padY} ${padX} ${fs}`}
      style={{
        background: active ? bg : "transparent",
        borderColor: active ? bd : "oklch(0.92 0.005 250)",
        color: active ? fg : "oklch(0.55 0.012 250)",
      }}
    >
      <span
        className="size-1.5 rounded-full"
        style={{ background: active ? dot : "oklch(0.92 0.005 250)" }}
      />
      {c.label}
    </span>
  );
}
