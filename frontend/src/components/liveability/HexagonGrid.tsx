"use client";

import { useMemo, useState } from "react";
import { ASPECT_LABEL, AspectKey } from "./reddit-types";

export type HexRow = {
  suburb: string;
  post_count: number;
  score: number | null;
  top_aspect: AspectKey | null;
  bottom_aspect: AspectKey | null;
  dominant_emotion: string | null;
  cached: boolean;
};

type HexagonGridProps = {
  rows: HexRow[];
  onSelect: (suburb: string) => void;
  hexSize?: number;
  columns?: number;
};

type HexLayoutItem = {
  cx: number;
  cy: number;
  row: HexRow;
};

/** Return the 6 vertex coordinates of a pointy-top hexagon. */
function hexPoints(cx: number, cy: number, size: number): string {
  const points: string[] = [];
  for (let i = 0; i < 6; i += 1) {
    const angleDeg = 60 * i - 30;
    const angleRad = (Math.PI / 180) * angleDeg;
    const x = cx + size * Math.cos(angleRad);
    const y = cy + size * Math.sin(angleRad);
    points.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }
  return points.join(" ");
}

/** Map a 0..1 score to a red → amber → green tailwindy hex colour. */
function scoreColour(score: number | null): string {
  if (score === null) return "#e2e8f0"; // slate-200 for no-data
  if (score >= 0.65) return "#10b981"; // emerald-500
  if (score >= 0.55) return "#34d399"; // emerald-400
  if (score >= 0.5) return "#a7f3d0"; // emerald-200
  if (score >= 0.45) return "#fde68a"; // amber-200
  if (score >= 0.4) return "#fbbf24"; // amber-400
  if (score >= 0.3) return "#f87171"; // red-400
  return "#ef4444"; // red-500
}

function scoreTextColour(score: number | null): string {
  if (score === null) return "#64748b"; // slate-500
  if (score >= 0.5) return "#064e3b"; // emerald-900
  return "#7f1d1d"; // red-900
}

export function HexagonGrid({
  rows,
  onSelect,
  hexSize = 38,
  columns = 12,
}: HexagonGridProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const { layout, width, height } = useMemo(() => {
    // Pointy-top geometry
    const hexWidth = Math.sqrt(3) * hexSize;
    const hexHeight = 2 * hexSize;
    const horizStep = hexWidth;
    const vertStep = hexHeight * 0.75;
    const paddingX = hexWidth / 2 + 8;
    const paddingY = hexSize + 8;

    const items: HexLayoutItem[] = rows.map((row, index) => {
      const rowIndex = Math.floor(index / columns);
      const colIndex = index % columns;
      const offsetX = rowIndex % 2 === 1 ? horizStep / 2 : 0;
      const cx = paddingX + colIndex * horizStep + offsetX;
      const cy = paddingY + rowIndex * vertStep;
      return { cx, cy, row };
    });

    const maxRow = Math.ceil(rows.length / columns);
    const totalWidth =
      paddingX * 2 + columns * horizStep + (maxRow > 1 ? horizStep / 2 : 0);
    const totalHeight = paddingY * 2 + (maxRow - 1) * vertStep + hexSize;

    return { layout: items, width: totalWidth, height: totalHeight };
  }, [rows, hexSize, columns]);

  const hoveredItem = useMemo(
    () => layout.find((item) => item.row.suburb === hovered) ?? null,
    [layout, hovered]
  );

  return (
    <div className="relative">
      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible"
        role="img"
        aria-label="Hexagon overview of Sydney suburbs"
      >
        {layout.map(({ cx, cy, row }) => {
          const colour = scoreColour(row.score);
          const textColour = scoreTextColour(row.score);
          const active = hovered === row.suburb;
          const points = hexPoints(cx, cy, hexSize);
          const label = row.suburb.length > 11
            ? `${row.suburb.slice(0, 10)}…`
            : row.suburb;
          const scoreLabel =
            row.score !== null ? Math.round(row.score * 100) : "—";
          return (
            <g
              key={row.suburb}
              onMouseEnter={() => setHovered(row.suburb)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onSelect(row.suburb)}
              style={{ cursor: "pointer" }}
            >
              <polygon
                points={points}
                fill={colour}
                fillOpacity={active ? 1 : row.cached ? 0.88 : 0.55}
                stroke={active ? "#0f172a" : "#ffffff"}
                strokeWidth={active ? 2 : 1.2}
              />
              <text
                x={cx}
                y={cy - 2}
                textAnchor="middle"
                fontSize={Math.max(9, hexSize * 0.26)}
                fontWeight={700}
                fill={textColour}
                style={{ pointerEvents: "none" }}
              >
                {label}
              </text>
              <text
                x={cx}
                y={cy + 14}
                textAnchor="middle"
                fontSize={Math.max(10, hexSize * 0.32)}
                fontWeight={800}
                fill={textColour}
                style={{ pointerEvents: "none" }}
              >
                {scoreLabel}
              </text>
            </g>
          );
        })}
      </svg>

      {hoveredItem ? (
        <div
          className="pointer-events-none absolute z-20 -translate-x-1/2 rounded-xl border border-slate-200 bg-white/98 px-3 py-2 text-[11px] shadow-cardLg"
          style={{
            left: `${(hoveredItem.cx / width) * 100}%`,
            top: `${(hoveredItem.cy / height) * 100}%`,
            transform: "translate(-50%, -120%)",
          }}
        >
          <p className="font-bold text-slate-900">{hoveredItem.row.suburb}</p>
          <p className="mt-1 text-slate-600">
            {hoveredItem.row.score !== null
              ? `Liveability ${Math.round(hoveredItem.row.score * 100)} / 100`
              : "No NLP analysis cached yet"}
          </p>
          <p className="text-slate-500">
            {hoveredItem.row.post_count.toLocaleString()} posts
          </p>
          {hoveredItem.row.top_aspect ? (
            <p className="mt-1 text-emerald-700">
              ↑ {ASPECT_LABEL[hoveredItem.row.top_aspect as AspectKey]}
            </p>
          ) : null}
          {hoveredItem.row.bottom_aspect &&
          hoveredItem.row.bottom_aspect !== hoveredItem.row.top_aspect ? (
            <p className="text-rose-600">
              ↓ {ASPECT_LABEL[hoveredItem.row.bottom_aspect as AspectKey]}
            </p>
          ) : null}
          {hoveredItem.row.dominant_emotion ? (
            <p className="mt-1 text-slate-500">
              mood: {hoveredItem.row.dominant_emotion}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
