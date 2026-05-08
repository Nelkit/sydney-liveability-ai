"use client";

import { useState } from "react";
import { SourceBadge } from "@/components/ui/SourceBadge";
import type { Citation, SourceKind } from "@/types/api";

type Props = {
  citations: Citation[];
};

const SOURCE_KIND_LIST: SourceKind[] = ["reddit", "bocsar", "arcgis", "osm", "tfnsw", "pdf"];

function isSourceKind(v: unknown): v is SourceKind {
  return typeof v === "string" && SOURCE_KIND_LIST.includes(v as SourceKind);
}

export function InlineCitations({ citations }: Props) {
  const [active, setActive] = useState<Citation | null>(null);

  if (!citations.length) return null;

  const deduped = Array.from(new Map(citations.map((c) => [c.n, c])).values());

  function toggle(c: Citation) {
    setActive((prev) => (prev?.n === c.n ? null : c));
  }

  const activeSrc = active && isSourceKind(active.src) ? active.src : null;

  return (
    <div className="mt-3 flex flex-col gap-1.5">
      {/* Badge row */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-fg-muted">
          cites
        </span>
        {deduped.map((c) => {
          const isActive = active?.n === c.n;
          return (
            <button
              key={c.n}
              type="button"
              onClick={() => toggle(c)}
              className="inline-flex cursor-pointer items-center gap-[3px] rounded-[3px] border px-[5px] py-[2px] font-mono text-[10px] leading-none transition-colors duration-[120ms]"
              style={{
                background:  isActive ? "oklch(0.55 0.18 285)" : "oklch(0.975 0.004 250)",
                borderColor: isActive ? "oklch(0.55 0.18 285)" : "oklch(0.92 0.005 250)",
                color:       isActive ? "white"                 : "oklch(0.18 0.01 250)",
              }}
            >
              {c.n}
            </button>
          );
        })}
      </div>

      {/* Expanded citation detail — slides in below the badges */}
      {active && (
        <div
          className="flex flex-col gap-2 rounded-lg border p-2.5 text-[12px] leading-[1.55]"
          style={{
            borderColor: "oklch(0.88 0.05 285)",
            background:  "oklch(0.98 0.015 285)",
          }}
        >
          <div className="flex flex-wrap items-center gap-1.5">
            {activeSrc && <SourceBadge kind={activeSrc} />}
            {active.suburbs.map((s) => (
              <span
                key={s}
                className="rounded px-1.5 py-px font-mono text-[10px] text-white"
                style={{ background: "oklch(0.55 0.18 285)" }}
              >
                @{s}
              </span>
            ))}
          </div>
          <p className="text-fg">{active.detail}</p>
        </div>
      )}
    </div>
  );
}
