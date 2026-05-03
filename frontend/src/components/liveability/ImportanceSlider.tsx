"use client";

import { useRef, useState } from "react";
import { importanceOptions } from "./data";
import { ImportanceLevelKey } from "./types";

function sliderColor(n: number) {
  if (n >= 8) return { track: "#f43f5e", thumb: "#e11d48" };
  if (n >= 5) return { track: "#f59e0b", thumb: "#d97706" };
  return { track: "#94a3b8", thumb: "#64748b" };
}

type ImportanceSliderProps = {
  value: ImportanceLevelKey | undefined;
  onChange: (key: ImportanceLevelKey) => void;
};

export function ImportanceSlider({ value, onChange }: ImportanceSliderProps) {
  const committed = value ? parseInt(value) : 5;
  const [dragging, setDragging] = useState<number | null>(null);
  const isDragging = useRef(false);

  const current = dragging ?? committed;
  const { track, thumb } = sliderColor(current);
  const pct = ((current - 1) / 9) * 100;

  function commit(val: number) {
    isDragging.current = false;
    setDragging(null);
    onChange(String(val) as ImportanceLevelKey);
  }

  return (
    <div className="w-full">
      <div className="px-1">
        <input
          type="range"
          min={1}
          max={10}
          step={1}
          value={current}
          onChange={(e) => {
            isDragging.current = true;
            setDragging(parseInt(e.target.value));
          }}
          onMouseUp={(e) => commit(parseInt((e.target as HTMLInputElement).value))}
          onTouchEnd={(e) => commit(parseInt((e.target as HTMLInputElement).value))}
          onKeyUp={(e) => commit(parseInt((e.target as HTMLInputElement).value))}
          className="h-2 w-full cursor-pointer appearance-none rounded-full outline-none focus-visible:ring-2 focus-visible:ring-slate-400/60"
          style={{
            background: `linear-gradient(to right, ${track} ${pct}%, #e2e8f0 ${pct}%)`,
            accentColor: thumb,
          }}
        />
      </div>
      <div className="mt-1.5 flex justify-between px-1">
        {importanceOptions.map((o) => {
          const active = parseInt(o.key) === current;
          return (
            <span
              key={o.key}
              className={`text-[10px] font-semibold transition-colors ${active ? "text-slate-800" : "text-slate-300"}`}
            >
              {o.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
