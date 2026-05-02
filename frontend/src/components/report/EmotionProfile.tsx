import { Bar } from "@/components/ui/Bar";
import type { EmotionProfile as EmotionProfileType } from "@/types/api";

const EMOTION_COLORS: Record<string, string> = {
  joy:      "oklch(0.72 0.16 75)",
  surprise: "oklch(0.65 0.16 195)",
  neutral:  "oklch(0.65 0.02 250)",
  sadness:  "oklch(0.55 0.14 270)",
  fear:     "oklch(0.50 0.16 305)",
  anger:    "oklch(0.55 0.18 25)",
  disgust:  "oklch(0.55 0.16 145)",
};

type Props = { data: EmotionProfileType };

export function EmotionProfile({ data }: Props) {
  const max = Math.max(...Object.values(data));
  return (
    <div className="flex flex-col gap-2">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="grid items-center gap-2.5" style={{ gridTemplateColumns: "70px 1fr 30px" }}>
          <div className="text-[11.5px] capitalize text-fg">{k}</div>
          <Bar value={v} max={max} color={EMOTION_COLORS[k] ?? "oklch(0.55 0.18 285)"} height={6} />
          <div className="text-right font-mono text-[11.5px] font-semibold">{v}</div>
        </div>
      ))}
    </div>
  );
}
