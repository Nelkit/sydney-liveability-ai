"use client";

import { useCitationHover } from "@/context/CitationHoverContext";
import type { Citation } from "@/types/api";

type Props = {
  citation: Citation;
};

const CONFIDENCE_DOT: Record<string, string> = {
  high:   "bg-sent-pos",
  medium: "bg-sent-neu",
  low:    "bg-sent-neg",
};

function confidenceLevel(retrieved?: number): "high" | "medium" | "low" {
  if (!retrieved) return "low";
  if (retrieved >= 10) return "high";
  if (retrieved >= 4)  return "medium";
  return "low";
}

export function Cite({ citation }: Props) {
  const { hoveredCite, setHoveredCite } = useCitationHover();
  const isActive = hoveredCite?.n === citation.n;
  const level = confidenceLevel(citation.retrieved);
  const dotClass = CONFIDENCE_DOT[level];

  return (
    <sup
      onMouseEnter={() => setHoveredCite(citation)}
      onMouseLeave={() => setHoveredCite(null)}
      className="relative -top-px ml-0.5 inline-flex cursor-pointer items-center gap-[3px] rounded-[3px] border px-[5px] py-px font-mono text-[10px] leading-none transition-colors duration-[120ms]"
      style={{
        background:  isActive ? "oklch(0.55 0.18 285)" : "oklch(0.975 0.004 250)",
        borderColor: isActive ? "oklch(0.55 0.18 285)" : "oklch(0.92 0.005 250)",
        color:       isActive ? "white" : "oklch(0.18 0.01 250)",
      }}
    >
      <span className={`size-[5px] rounded-full ${dotClass}`} />
      {citation.n}
    </sup>
  );
}
