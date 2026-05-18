"use client";

import { ArrowRight, Square } from "lucide-react";
import { useEffect, useRef } from "react";

const SUGGESTION_CHIPS = [
  { label: "Is Redfern safe at night?",                       kind: "crime"      },
  { label: "Which inner-west suburbs have the most parks?",   kind: "gis"        },
  { label: "What do residents say about housing in Newtown?", kind: "sentiment"  },
  { label: "Compare Glebe vs Newtown for a quiet lifestyle",  kind: "comparator" },
] as const;

const KIND_ACCENT: Record<string, string> = {
  crime:      "oklch(0.55 0.18 25)",
  gis:        "oklch(0.55 0.16 235)",
  sentiment:  "oklch(0.55 0.16 75)",
  comparator: "oklch(0.55 0.18 285)",
};

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  isLoading?: boolean;
  onCancel?: () => void;
};

export function ChatInput({
  value,
  onChange,
  onSend,
  isLoading,
  onCancel,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) onSend();
    }
  }

  // Auto-focus on mount
  useEffect(() => { inputRef.current?.focus(); }, []);

  return (
    <div className="border-t border-border px-4 pb-4 pt-3">
      {/* Suggestion chips */}
      <div className="mb-2.5 hidden flex-wrap gap-1.5 sm:flex">
        {SUGGESTION_CHIPS.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => { onChange(s.label); setTimeout(onSend, 0); }}
            className="cursor-pointer rounded-full border border-border bg-bg-elev px-[10px] py-[5px] text-[11px] text-fg transition hover:border-[var(--chip-accent)] hover:text-[var(--chip-accent)]"
            style={{ "--chip-accent": KIND_ACCENT[s.kind] } as React.CSSProperties}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Input row */}
      <div className="flex text-base items-center gap-2 rounded-[10px] border border-border bg-bg px-3.5 py-2 shadow-[0_1px_0_oklch(0.96_0.005_250)]">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about transport, safety, vibes…"
          className="flex-1 border-none bg-transparent text-base text-fg placeholder:text-fg-muted outline-none"
        />

        {/* Cancel button — visible after 3s of loading */}
        {isLoading && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="flex cursor-pointer items-center gap-1 rounded-md border border-sent-neg/50 bg-sent-neg/10 px-2 py-1 font-mono text-[10px] text-sent-neg transition hover:bg-sent-neg/20"
          >
            <Square size={9} />
            Stop
          </button>
        )}

        <button
          type="button"
          onClick={onSend}
          disabled={isLoading || !value.trim()}
          className="flex size-8 cursor-pointer items-center justify-center rounded-lg border-none bg-fg text-bg transition disabled:opacity-40 hover:opacity-80"
        >
          <ArrowRight size={14} strokeWidth={1.4} />
        </button>
      </div>

      {/* Footer row */}
      <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-fg-muted">
        <span>Reddit r/sydney · BOCSAR · ArcGIS · OSM · GTFS Transport · City of Sydney</span>
        <span>cited &amp; grounded</span>
      </div>
    </div>
  );
}
