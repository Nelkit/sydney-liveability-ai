"use client";

import {
  EMOTION_COLOR,
  EMOTION_ORDER,
  EmotionKey,
} from "./reddit-types";

type EmotionBarsProps = {
  emotions: Partial<Record<EmotionKey, number>>;
};

export function EmotionBars({ emotions }: EmotionBarsProps) {
  const values = EMOTION_ORDER.map((key) => ({
    key,
    value: Math.max(0, Math.min(1, emotions[key] ?? 0)),
  }));
  const max = Math.max(0.05, ...values.map((v) => v.value));

  return (
    <div className="space-y-1.5">
      {values.map((row) => {
        const width = Math.round((row.value / max) * 100);
        return (
          <div key={row.key} className="flex items-center gap-2">
            <span className="w-16 text-[11px] font-medium capitalize text-slate-600">
              {row.key}
            </span>
            <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${width}%`,
                  backgroundColor: EMOTION_COLOR[row.key],
                }}
              />
            </div>
            <span className="w-9 text-right text-[11px] tabular-nums text-slate-500">
              {Math.round(row.value * 100)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
