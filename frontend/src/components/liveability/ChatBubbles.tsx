"use client";

import { ArrowRight, BookOpen } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { Cite } from "@/components/ui/Cite";
import { SourceBadge } from "@/components/ui/SourceBadge";
import type { AssistantMessage, SourceKind } from "@/types/api";

// ---- UserBubble ----

type UserBubbleProps = {
  text: string;
  ts?: string;
};

export function UserBubble({ text, ts }: UserBubbleProps) {
  return (
    <div className="flex flex-col items-end gap-1 self-end" style={{ maxWidth: "90%" }}>
      <div className="rounded-[16px_6px_16px_16px] bg-fg px-4 py-3 text-sm leading-relaxed text-bg shadow-floatLg">
        {text}
      </div>
      {ts && (
        <div className="font-mono text-[10px] text-fg-muted">you · {ts}</div>
      )}
    </div>
  );
}

// ---- AssistantBubble ----

type AssistantBubbleProps = {
  message: AssistantMessage;
  onOpenReport?: (suburbs: string[]) => void;
  followUpChips?: string[];
  onFollowUp?: (text: string) => void;
};

// Groups sources by kind and counts them
function groupSources(sources: SourceKind[]): { kind: SourceKind; n: number }[] {
  const counts = new Map<SourceKind, number>();
  for (const s of sources) counts.set(s, (counts.get(s) ?? 0) + 1);
  return Array.from(counts.entries()).map(([kind, n]) => ({ kind, n }));
}

const STREAM_INTERVAL_MS = 18;

function useStreamedClaims(claims: AssistantMessage["claims"]) {
  const fullText = claims.map((cl) => cl.text).join(" ");
  const words = fullText.split(" ").filter(Boolean);
  const [visibleCount, setVisibleCount] = useState(0);
  const isDone = visibleCount >= words.length;

  useEffect(() => {
    setVisibleCount(0);
  }, [fullText]);

  useEffect(() => {
    if (isDone) return;
    const id = setInterval(() => {
      setVisibleCount((n) => {
        const next = n + 1;
        if (next >= words.length) clearInterval(id);
        return next;
      });
    }, STREAM_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fullText, isDone]); // eslint-disable-line react-hooks/exhaustive-deps

  const streamedText = words.slice(0, visibleCount).join(" ");
  return { streamedText, isDone };
}

export function AssistantBubble({
  message,
  onOpenReport,
  followUpChips,
  onFollowUp,
}: AssistantBubbleProps) {
  const { router, claims, summary, ts } = message;
  const categories = Array.isArray(router?.categories) ? router.categories : [];
  const suburbs = Array.isArray(router?.suburbs) ? router.suburbs : [];
  const latencyMs = typeof router?.latencyMs === "number" ? router.latencyMs : 0;

  const { streamedText, isDone } = useStreamedClaims(claims);

  // Deduplicate all sources across all citations
  const allSources: SourceKind[] = claims.flatMap((cl) => cl.cites.map((c) => c.src));
  const groupedSources = groupSources(allSources);

  return (
    <div className="flex flex-col gap-2.5">
      {/* Router chips row */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 font-mono text-[10px] uppercase tracking-[0.06em] text-fg-muted">
          route
        </span>
        {categories.map((c) => (
          <CategoryChip key={c} kind={c} />
        ))}
        <span className="flex-1" />
        <span className="font-mono text-[10px] text-fg-muted">
          {suburbs.map((s) => `@${s}`).join(" · ")}
          {latencyMs > 0 && ` · ${latencyMs}ms`}
        </span>
        {ts && (
          <span className="font-mono text-[10px] text-fg-muted">{ts}</span>
        )}
      </div>

      {/* Answer body */}
      <div className="rounded-[6px_16px_16px_16px] border border-border bg-bg p-4 text-sm leading-relaxed text-fg shadow-float backdrop-blur">
        <span>
          {streamedText}
          {!isDone && (
            <span className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[1px] animate-pulse rounded-sm bg-fg-muted" />
          )}
        </span>

        {/* Citations and report CTA only after streaming finishes */}
        {isDone && (
          <>
            {claims.some((cl) => cl.cites.length > 0) && (
              <span className="ml-1">
                {claims.flatMap((cl) => cl.cites).map((c) => (
                  <Cite key={c.n} citation={c} />
                ))}
              </span>
            )}

            {summary && summary.suburbs.length > 0 && (
              <div
                className="mt-3.5 flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5"
                style={{
                  background: "linear-gradient(180deg, oklch(0.97 0.025 285), oklch(0.99 0.01 285))",
                  borderColor: "oklch(0.88 0.05 285)",
                }}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {summary.suburbs.map((s, i) => (
                    <span key={s} className="flex items-center gap-1.5">
                      {i > 0 && <span className="font-mono text-[10px] text-fg-muted">vs</span>}
                      <span
                        className="rounded-md px-2 py-0.5 font-mono text-[11px] font-semibold text-white"
                        style={{ background: i === 0 ? "oklch(0.55 0.18 285)" : "oklch(0.62 0.16 75)" }}
                      >
                        {s}
                      </span>
                    </span>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => onOpenReport?.(summary.suburbs)}
                  className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-md border border-border bg-bg px-[10px] py-1.5 text-[11.5px] font-medium text-fg transition hover:bg-bg-elev"
                >
                  {summary.suburbs.length >= 2 ? "Compare" : "Open report"}
                  <ArrowRight size={12} strokeWidth={1.4} />
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Sources strip — only after streaming finishes */}
      {isDone && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-fg-muted">
            sources
          </span>
          {groupedSources.map(({ kind, n }) => (
            <SourceBadge key={kind} kind={kind} n={n} />
          ))}
          <span className="flex-1" />
          <FeedbackButtons />
        </div>
      )}

      {/* Follow-up suggestion chips */}
      {isDone && followUpChips && followUpChips.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {followUpChips.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => onFollowUp?.(chip)}
              className="cursor-pointer rounded-full border border-border bg-bg-elev px-[10px] py-[5px] text-[11px] text-fg transition hover:border-accent hover:text-accent"
            >
              {chip}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function FeedbackButtons() {
  return (
    <div className="flex gap-1">
      <button
        type="button"
        title="Helpful"
        className="flex size-6 cursor-pointer items-center justify-center rounded-md border border-border bg-bg text-fg transition hover:bg-bg-elev"
      >
        <svg width="11" height="11" viewBox="0 0 14 14">
          <path d="M3 6h2v6H3zm3 0v6h4l1.5-4-1-2H8V3a1 1 0 0 0-2 0z" fill="none" stroke="currentColor" strokeWidth="1.2" />
        </svg>
      </button>
      <button
        type="button"
        title="Not helpful"
        className="flex size-6 cursor-pointer items-center justify-center rounded-md border border-border bg-bg text-fg transition hover:bg-bg-elev"
      >
        <svg width="11" height="11" viewBox="0 0 14 14" style={{ transform: "rotate(180deg)" }}>
          <path d="M3 6h2v6H3zm3 0v6h4l1.5-4-1-2H8V3a1 1 0 0 0-2 0z" fill="none" stroke="currentColor" strokeWidth="1.2" />
        </svg>
      </button>
    </div>
  );
}

// ---- Out-of-scope empty state ----

const SUBURB_SUGGESTIONS = ["Newtown", "Glebe", "Redfern", "Surry Hills"];

type OutOfScopeStateProps = {
  onSuburbClick: (suburb: string) => void;
};

export function OutOfScopeState({ onSuburbClick }: OutOfScopeStateProps) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-bg-elev p-4">
      <p className="text-[13.5px] leading-[1.65] text-fg-muted">
        I noticed your question doesn&apos;t mention a specific suburb. Try one of these:
      </p>
      <div className="flex flex-wrap gap-2">
        {SUBURB_SUGGESTIONS.map((suburb) => (
          <button
            key={suburb}
            type="button"
            onClick={() => onSuburbClick(`Tell me about ${suburb}`)}
            className="cursor-pointer rounded-full border border-accent/40 bg-accent/5 px-3 py-1.5 text-[12px] font-medium text-accent transition hover:bg-accent/10"
          >
            {suburb}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---- Typing indicator ----

const TYPING_PHRASES = [
  "Thinking…",
  "Searching Reddit…",
  "Checking crime data…",
  "Analysing sentiment…",
  "Reading GIS layers…",
  "Comparing suburbs…",
  "Scoring liveability…",
  "Processing…",
  "Almost there…",
];

export function TypingBubble({ step }: { step?: string }) {
  const [phraseIdx, setPhraseIdx] = useState(0);

  useEffect(() => {
    if (step) return;
    const id = setInterval(() => {
      setPhraseIdx((i) => (i + 1) % TYPING_PHRASES.length);
    }, 1800);
    return () => clearInterval(id);
  }, [step]);

  return (
    <div className="flex flex-col gap-1.5 rounded-[6px_16px_16px_16px] border border-border bg-bg px-4 py-3 shadow-float backdrop-blur">
      <div className="flex items-center gap-1.5">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-fg-muted"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
      <span className="font-mono text-[10px] text-fg-muted transition-all duration-500">
        {step ?? TYPING_PHRASES[phraseIdx]}
      </span>
    </div>
  );
}

// ---- Skeleton ----

export function AssistantBubbleSkeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-2.5">
      <div className="flex gap-1.5">
        <div className="h-5 w-14 rounded-full bg-bg-elev" />
        <div className="h-5 w-20 rounded-full bg-bg-elev" />
        <div className="h-5 w-16 rounded-full bg-bg-elev" />
      </div>
      <div className="rounded-[6px_16px_16px_16px] border border-border bg-bg p-4 shadow-float backdrop-blur space-y-2">
        <div className="h-3 w-full rounded bg-bg-elev" />
        <div className="h-3 w-5/6 rounded bg-bg-elev" />
        <div className="h-3 w-4/6 rounded bg-bg-elev" />
      </div>
      <div className="flex gap-1.5">
        <div className="h-5 w-16 rounded bg-bg-elev" />
        <div className="h-5 w-16 rounded bg-bg-elev" />
      </div>
    </div>
  );
}
