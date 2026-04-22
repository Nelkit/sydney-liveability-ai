"use client";

import { useEffect, useMemo, useState } from "react";
import { AspectRadar } from "./AspectRadar";
import { EmotionBars } from "./EmotionBars";
import {
  ASPECT_LABEL,
  ASPECT_ORDER,
  AspectKey,
  SuburbAnalysis,
} from "./reddit-types";

interface RedditNLPAnalysisProps {
  suburb: string | null;
}

const API_BASE =
  (typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_API_URL &&
    process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")) ||
  "http://localhost:8000";

type FetchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; data: SuburbAnalysis }
  | { status: "error"; message: string };

function formatRelative(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diff = Math.max(0, now - then);
    const minutes = Math.round(diff / 60000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.round(hours / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

function LegendDots() {
  return (
    <div className="flex items-center gap-2 text-[10px] text-slate-500">
      <span className="inline-flex items-center gap-1">
        <span className="h-2 w-2 rounded-full bg-emerald-500" /> positive
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-2 w-2 rounded-full bg-amber-500" /> neutral
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-2 w-2 rounded-full bg-rose-500" /> negative
      </span>
    </div>
  );
}

function Highlight({
  label,
  aspectKey,
  score,
  mentions,
  tone,
}: {
  label: string;
  aspectKey?: AspectKey;
  score?: number;
  mentions?: number;
  tone: "positive" | "negative";
}) {
  const colourClass =
    tone === "positive"
      ? "border-emerald-100 bg-emerald-50 text-emerald-800"
      : "border-rose-100 bg-rose-50 text-rose-800";
  if (!aspectKey) {
    return (
      <div className={`rounded-xl border ${colourClass} p-3 opacity-60`}>
        <p className="text-[10px] font-bold uppercase tracking-[0.14em]">
          {label}
        </p>
        <p className="mt-1 text-[13px] font-semibold">Not enough data</p>
      </div>
    );
  }
  return (
    <div className={`rounded-xl border ${colourClass} p-3`}>
      <p className="text-[10px] font-bold uppercase tracking-[0.14em]">
        {label}
      </p>
      <p className="mt-1 text-[13px] font-semibold">
        {ASPECT_LABEL[aspectKey]}
      </p>
      <p className="mt-1 text-[11px] opacity-80">
        {Math.round((score ?? 0.5) * 100)} / 100 · {mentions ?? 0} mentions
      </p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
        <div className="mx-auto flex h-[420px] w-[420px] max-w-full items-center justify-center">
          <div className="h-64 w-64 animate-pulse rounded-full bg-slate-100" />
        </div>
      </div>
      <div className="flex flex-col gap-6">
        <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
          <div className="h-4 w-32 animate-pulse rounded-full bg-slate-100" />
          <div className="mt-4 space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-3 animate-pulse rounded-full bg-slate-100"
                style={{ width: `${95 - i * 8}%` }}
              />
            ))}
          </div>
        </div>
        <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
          <div className="h-4 w-20 animate-pulse rounded-full bg-slate-100" />
          <div className="mt-3 grid grid-cols-2 gap-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="rounded-xl border border-slate-200 bg-slate-50 p-3"
              >
                <div className="h-3 w-16 animate-pulse rounded-full bg-slate-200" />
                <div className="mt-2 h-3 w-32 animate-pulse rounded-full bg-slate-100" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="mt-4 rounded-xl2 border border-rose-200 bg-rose-50 p-8 text-center">
      <p className="text-sm font-semibold text-rose-900">Failed to load analysis</p>
      <p className="mt-2 text-[13px] text-rose-800">{message}</p>
    </div>
  );
}

export function RedditNLPAnalysis({ suburb }: RedditNLPAnalysisProps) {
  const [state, setState] = useState<FetchState>({ status: "idle" });

  useEffect(() => {
    if (!suburb) {
      setState({ status: "idle" });
      return;
    }

    let cancelled = false;
    setState({ status: "loading" });

    const url = `${API_BASE}/api/reddit/${encodeURIComponent(suburb)}`;

    fetch(url, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.text().catch(() => "");
          throw new Error(
            `Request failed (${res.status}): ${body.slice(0, 200) || res.statusText}`
          );
        }
        return (await res.json()) as SuburbAnalysis;
      })
      .then((data) => {
        if (!cancelled) {
          setState({ status: "ok", data });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Unknown error loading analysis";
        setState({ status: "error", message });
      });

    return () => {
      cancelled = true;
    };
  }, [suburb]);

  const topAspects = useMemo(() => {
    if (state.status !== "ok") return [];
    return ASPECT_ORDER.map((key) => ({
      key,
      ...state.data.aspects[key],
    }))
      .filter((row) => row.mentions > 0)
      .sort((a, b) => b.score - a.score);
  }, [state]);

  const bestAspect = topAspects[0];
  const worstAspect = topAspects[topAspects.length - 1];

  return (
    <section className="mt-6 rounded-xl2 border border-slate-200 bg-slate-50/70 p-4 sm:p-6">
      <div className="mb-4">
        <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
          Reddit NLP Analysis
        </h3>
        <p className="mt-1 text-[12px] text-slate-600">
          {suburb
            ? `Deep-dive analysis for ${suburb}`
            : "Select a suburb from the map to load suburb-specific Reddit analysis."}
        </p>
      </div>

      {state.status === "idle" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-[13px] text-slate-600">
          Suburb context is not available for this response yet.
        </div>
      ) : state.status === "loading" ? (
        <LoadingSkeleton />
      ) : state.status === "error" ? (
        <ErrorCard message={state.message} />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3 text-[11px] font-medium text-slate-600 mb-6">
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
              {state.data.post_count.toLocaleString()} posts analysed
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
              Updated {formatRelative(state.data.fetched_at)}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                    Aspect radar
                  </h3>
                  <p className="mt-1 text-[12px] text-slate-500">
                    Each axis is a liveability dimension · filled area shows
                    weighted sentiment score (0-100).
                  </p>
                </div>
                <LegendDots />
              </div>
              <div className="flex justify-center">
                <AspectRadar aspects={state.data.aspects} />
              </div>
            </div>

            <div className="flex flex-col gap-6">
              <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
                <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                  Emotion profile
                </h3>
                <p className="mt-1 text-[12px] text-slate-500">
                  DistilRoBERTa emotion detection averaged across posts.
                </p>
                <div className="mt-4">
                  <EmotionBars emotions={state.data.emotions} />
                </div>
              </div>

              <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
                <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                  Highlights
                </h3>
                <div className="mt-3 grid grid-cols-2 gap-3 text-[13px]">
                  <Highlight
                    label="Loved for"
                    aspectKey={bestAspect?.key}
                    score={bestAspect?.score}
                    mentions={bestAspect?.mentions}
                    tone="positive"
                  />
                  <Highlight
                    label="Concerns"
                    aspectKey={worstAspect?.key}
                    score={worstAspect?.score}
                    mentions={worstAspect?.mentions}
                    tone="negative"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
            <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
              Community narrative
            </h3>
            <p className="mt-3 whitespace-pre-wrap text-[14px] leading-relaxed text-slate-700">
              {state.data.narrative || "No narrative available."}
            </p>
          </div>

          {state.data.sources.length > 0 ? (
            <div className="mt-6 rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
              <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                Top source posts
              </h3>
              <p className="mt-1 text-[12px] text-slate-500">
                Highest-scored posts that fed the analysis.
              </p>
              <ul className="mt-4 space-y-3">
                {state.data.sources.slice(0, 8).map((source, idx) => (
                  <li
                    key={`${source.url}-${idx}`}
                    className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 transition hover:border-slate-200 hover:bg-white"
                  >
                    <div className="flex items-start gap-3">
                      <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-orange-600 flex-shrink-0">
                        {source.score}
                      </span>
                      <div className="flex-1 text-[13px] text-slate-700">
                        <p className="line-clamp-3 whitespace-pre-wrap">
                          {source.text}
                        </p>
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-block text-[11px] font-semibold text-blue-600 hover:underline"
                        >
                          Open on Reddit
                        </a>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
