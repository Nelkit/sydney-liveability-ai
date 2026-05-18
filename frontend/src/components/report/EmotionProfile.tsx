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
        <div key={k} className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <div className="text-[11.5px] capitalize text-fg">{k}</div>
            <div className="font-mono text-[11.5px] font-semibold">{Math.round(v * 100)}%</div>
          </div>
          <Bar value={v} max={max} color={EMOTION_COLORS[k] ?? "oklch(0.55 0.18 285)"} height={6} />
        </div>
      ))}
    </div>
  );
}
