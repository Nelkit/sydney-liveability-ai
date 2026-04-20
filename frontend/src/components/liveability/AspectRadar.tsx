"use client";

import { useMemo, useState } from "react";
import {
  ASPECT_LABEL,
  ASPECT_ORDER,
  AspectKey,
  AspectScore,
} from "./reddit-types";

type AspectRadarProps = {
  aspects: Partial<Record<AspectKey, AspectScore>>;
  size?: number;
  accent?: string;
};

const RING_LEVELS = [0.25, 0.5, 0.75, 1.0];

function polarPoint(
  cx: number,
  cy: number,
  radius: number,
  angleDeg: number
) {
  const angle = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
}

function polygonPoints(
  cx: number,
  cy: number,
  radius: number,
  sides: number,
  values: number[] | null = null
) {
  const step = 360 / sides;
  const pts: string[] = [];
  for (let i = 0; i < sides; i += 1) {
    const r = values ? radius * values[i] : radius;
    const p = polarPoint(cx, cy, r, i * step);
    pts.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`);
  }
  return pts.join(" ");
}

function scoreColour(score: number) {
  // 0 = red-500, 0.5 = amber-500, 1 = emerald-500
  if (score >= 0.65) return "#10b981";
  if (score >= 0.45) return "#f59e0b";
  return "#ef4444";
}

export function AspectRadar({
  aspects,
  size = 420,
  accent = "#2563eb",
}: AspectRadarProps) {
  const [hovered, setHovered] = useState<AspectKey | null>(null);

  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.36;
  const sides = ASPECT_ORDER.length;

  const values = useMemo(
    () =>
      ASPECT_ORDER.map((key) => {
        const entry = aspects[key];
        return entry ? Math.max(0, Math.min(1, entry.score)) : 0.5;
      }),
    [aspects]
  );

  const dataPolygon = polygonPoints(cx, cy, radius, sides, values);

  // Axis endpoints and labels
  const axes = ASPECT_ORDER.map((key, i) => {
    const angle = (360 / sides) * i;
    const outer = polarPoint(cx, cy, radius, angle);
    const labelPos = polarPoint(cx, cy, radius + size * 0.095, angle);
    const vertex = polarPoint(cx, cy, radius * values[i], angle);
    return { key, outer, labelPos, vertex, angle };
  });

  const hoveredScore = hovered ? aspects[hovered] : null;

  return (
    <div className="relative flex flex-col items-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="overflow-visible"
        role="img"
        aria-label="Radar of liveability aspects from Reddit sentiment"
      >
        {/* Concentric rings */}
        {RING_LEVELS.map((level) => (
          <polygon
            key={level}
            points={polygonPoints(cx, cy, radius * level, sides)}
            fill="none"
            stroke="#e2e8f0"
            strokeWidth={1}
          />
        ))}
        <polygon
          points={polygonPoints(cx, cy, radius * 0.5, sides)}
          fill="none"
          stroke="#cbd5e1"
          strokeWidth={1}
          strokeDasharray="3,3"
        />

        {/* Spokes */}
        {axes.map((a) => (
          <line
            key={`spoke-${a.key}`}
            x1={cx}
            y1={cy}
            x2={a.outer.x}
            y2={a.outer.y}
            stroke="#e2e8f0"
            strokeWidth={1}
          />
        ))}

        {/* Data polygon */}
        <polygon
          points={dataPolygon}
          fill={accent}
          fillOpacity={0.14}
          stroke={accent}
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* Vertex dots */}
        {axes.map((a, i) => {
          const active = hovered === a.key;
          const colour = scoreColour(values[i]);
          return (
            <g
              key={`vertex-${a.key}`}
              onMouseEnter={() => setHovered(a.key)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: "pointer" }}
            >
              <circle
                cx={a.vertex.x}
                cy={a.vertex.y}
                r={active ? 7 : 5}
                fill={colour}
                stroke="#fff"
                strokeWidth={2}
              />
            </g>
          );
        })}

        {/* Axis labels */}
        {axes.map((a, i) => {
          const entry = aspects[a.key];
          const mentions = entry?.mentions ?? 0;
          const score = values[i];
          const active = hovered === a.key;
          const textAnchor =
            Math.abs(a.labelPos.x - cx) < 3
              ? "middle"
              : a.labelPos.x > cx
                ? "start"
                : "end";
          return (
            <g
              key={`label-${a.key}`}
              onMouseEnter={() => setHovered(a.key)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: "pointer" }}
            >
              <text
                x={a.labelPos.x}
                y={a.labelPos.y - 3}
                textAnchor={textAnchor}
                className={`text-[12px] font-semibold ${
                  active ? "fill-slate-900" : "fill-slate-700"
                }`}
              >
                {ASPECT_LABEL[a.key]}
              </text>
              <text
                x={a.labelPos.x}
                y={a.labelPos.y + 11}
                textAnchor={textAnchor}
                className="fill-slate-500 text-[10px]"
              >
                {mentions > 0
                  ? `${Math.round(score * 100)} · ${mentions} mentions`
                  : "no mentions"}
              </text>
            </g>
          );
        })}

        {/* Center score label */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="fill-slate-400 text-[10px] font-medium uppercase tracking-[0.14em]"
        >
          Liveability
        </text>
        <text
          x={cx}
          y={cy + 14}
          textAnchor="middle"
          className="fill-slate-700 text-[16px] font-bold"
        >
          {Math.round(
            (values.reduce((acc, v) => acc + v, 0) / values.length) * 100
          )}
        </text>
      </svg>

      {hoveredScore ? (
        <div className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white/95 px-3 py-1 text-[11px] text-slate-700 shadow-card">
          <span className="font-semibold">
            {ASPECT_LABEL[hovered as AspectKey]}
          </span>{" "}
          · score{" "}
          <span
            className="font-semibold"
            style={{ color: scoreColour(hoveredScore.score) }}
          >
            {Math.round(hoveredScore.score * 100)}
          </span>{" "}
          · {hoveredScore.mentions} mentions
        </div>
      ) : null}
    </div>
  );
}
