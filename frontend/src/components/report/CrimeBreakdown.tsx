import { Bar } from "@/components/ui/Bar";
import type { CrimeRow } from "@/types/api";

type Props = {
  data: CrimeRow[];
  crimeIdx?: number;
  sa4?: string;
};

export function CrimeBreakdown({ data, crimeIdx, sa4 }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-bg-elev p-4 font-mono text-[10.5px] text-fg-muted">
        Crime breakdown is not available for this suburb yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {data.map((c) => (
        <div key={c.cat} className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[12px] text-fg truncate">{c.cat}</div>
            <div className="flex shrink-0 items-center gap-2">
              <div className="font-mono text-[11.5px] font-semibold">{c.v}</div>
              <div
                className="font-mono text-[10.5px] font-semibold"
                style={{ color: c.trend < 0 ? "oklch(0.55 0.16 145)" : "oklch(0.55 0.18 25)" }}
              >
                {c.trend > 0 ? "+" : ""}{c.trend}%
              </div>
            </div>
          </div>
          <Bar value={c.v} max={500} color="oklch(0.55 0.18 25)" height={6} />
        </div>
      ))}
      {crimeIdx != null && (
        <div className="mt-3 flex items-center justify-between rounded-md border border-border bg-bg-elev px-[10px] py-2 font-mono text-[10.5px] text-fg-muted">
          <span>crime_index</span>
          <span className="font-semibold text-fg">{crimeIdx.toFixed(2)}</span>
        </div>
      )}
      {sa4 && (
        <div className="font-mono text-[10px] text-fg-muted">BOCSAR · {sa4} SA4 · per 100k · 2024</div>
      )}
    </div>
  );
}
