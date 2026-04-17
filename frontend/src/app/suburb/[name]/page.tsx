"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AspectRadar } from "../../../components/liveability/AspectRadar";
import { EmotionBars } from "../../../components/liveability/EmotionBars";
import { SharedBrand } from "../../../components/liveability/SharedBrand";
import {
  ASPECT_LABEL,
  ASPECT_ORDER,
  AspectKey,
  SuburbAnalysis,
} from "../../../components/liveability/reddit-types";

const API_BASE =
  (typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_API_URL &&
    process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")) ||
  "http://localhost:8000";

type FetchState =
  | { status: "loading" }
  | { status: "ok"; data: SuburbAnalysis }
  | { status: "error"; message: string };

function decodeSuburbParam(raw: string | string[] | undefined): string {
  if (!raw) return "";
  const value = Array.isArray(raw) ? raw[0] : raw;
  try {
    return decodeURIComponent(value).replace(/[-_]+/g, " ").trim();
  } catch {
    return value;
  }
}

function titleCase(input: string): string {
  return input
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1).toLowerCase())
    .join(" ");
}

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

export default function SuburbAnalysisPage() {
  const params = useParams();
  const suburbRaw = decodeSuburbParam(params?.name as string);
  const suburbName = useMemo(() => titleCase(suburbRaw), [suburbRaw]);

  const [state, setState] = useState<FetchState>({ status: "loading" });

  useEffect(() => {
    if (!suburbName) return;
    let cancelled = false;
    setState({ status: "loading" });

    const url = `${API_BASE}/api/reddit/${encodeURIComponent(suburbName)}`;

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
        if (!cancelled) setState({ status: "ok", data });
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
  }, [suburbName]);

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
    <main className="min-h-screen bg-[radial-gradient(circle_at_18%_12%,rgba(99,102,241,0.10),transparent_30%),linear-gradient(180deg,#f7f8fb,#eef1f7)] font-['Manrope',sans-serif] text-slateText">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/80 bg-white/70 px-5 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <SharedBrand compact />
          <div className="h-5 w-px bg-slate-200" />
          <Link
            href="/"
            className="text-[12px] font-semibold text-slate-600 transition hover:text-slate-900"
          >
            &larr; Back to map
          </Link>
        </div>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
          Reddit · NLP Insight
        </span>
      </header>

      <section className="mx-auto w-full max-w-6xl px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
              Suburb analysis
            </p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              {suburbName || "Unknown suburb"}
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              Sentiment, emotion, and community narrative distilled from Reddit
              discourse via our 8-dimension NLP pipeline.
            </p>
          </div>
          {state.status === "ok" ? (
            <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium text-slate-600">
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
                {state.data.post_count.toLocaleString()} posts analysed
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
                Updated {formatRelative(state.data.fetched_at)}
              </span>
            </div>
          ) : null}
        </div>

        {state.status === "loading" ? (
          <LoadingSkeleton />
        ) : state.status === "error" ? (
          <ErrorCard message={state.message} suburb={suburbName} />
        ) : (
          <>
            {/* Radar + emotions row */}
            <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
              <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                      Aspect radar
                    </h2>
                    <p className="mt-1 text-[12px] text-slate-500">
                      Each axis is a liveability dimension · filled area shows
                      weighted sentiment score (0–100).
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
                  <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                    Emotion profile
                  </h2>
                  <p className="mt-1 text-[12px] text-slate-500">
                    DistilRoBERTa emotion detection averaged across posts.
                  </p>
                  <div className="mt-4">
                    <EmotionBars emotions={state.data.emotions} />
                  </div>
                </div>

                <div className="rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
                  <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                    Highlights
                  </h2>
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

            {/* Narrative */}
            <div className="mt-6 rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
              <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                Community narrative
              </h2>
              <p className="mt-3 whitespace-pre-wrap text-[14px] leading-relaxed text-slate-700">
                {state.data.narrative || "No narrative available."}
              </p>
            </div>

            {/* Source posts */}
            {state.data.sources.length > 0 ? (
              <div className="mt-6 rounded-xl2 border border-slate-200 bg-white p-6 shadow-card">
                <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                  Top source posts
                </h2>
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
                        <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-orange-600">
                          ↑ {source.score}
                        </span>
                        <div className="flex-1 text-[13px] text-slate-700">
                          <p className="line-clamp-3 whitespace-pre-wrap">
                            {source.text}
                          </p>
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 inline-block text-[11px] font-semibold text-brandBlue hover:underline"
                          >
                            Open on Reddit ↗
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

      <footer className="mx-auto max-w-6xl px-5 pb-10 pt-2 text-center text-[11px] text-slate-400">
        NLP pipeline: BART-MNLI zero-shot · DistilRoBERTa emotion · VADER ·
        Claude synthesis (optional)
      </footer>
    </main>
  );
}

function LoadingSkeleton() {
  return (
    <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
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
      </div>
    </div>
  );
}

function ErrorCard({ message, suburb }: { message: string; suburb: string }) {
  const missingData =
    /no data|not found|404/i.test(message) ||
    /suburb/i.test(message);
  return (
    <div className="mt-10 rounded-xl2 border border-rose-200 bg-rose-50/60 p-6">
      <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-rose-700">
        {missingData ? "No Reddit analysis yet" : "Something went wrong"}
      </h2>
      <p className="mt-2 text-[13px] text-rose-800">
        {missingData
          ? `We don't have a pre-processed Reddit corpus for ${suburb} yet. Run the Arctic Shift bulk extractor for this suburb and retry.`
          : message}
      </p>
      <div className="mt-4 flex gap-2">
        <Link
          href="/"
          className="rounded-full border border-rose-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-rose-700 hover:border-rose-300"
        >
          Back to map
        </Link>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-full bg-rose-600 px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-rose-700"
        >
          Retry
        </button>
      </div>
    </div>
  );
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
