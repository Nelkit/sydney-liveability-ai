"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { CategoryChip } from "@/components/ui/CategoryChip";
import { Pill } from "@/components/ui/Pill";
import { ScoreGauge } from "@/components/ui/ScoreGauge";
import { SectionCard } from "@/components/ui/SectionCard";
import { Bar } from "@/components/ui/Bar";
import { AspectRadar } from "@/components/report/AspectRadar";
import { CrimeBreakdown } from "@/components/report/CrimeBreakdown";
import { EmotionProfile } from "@/components/report/EmotionProfile";
import { EvidenceTrace } from "@/components/report/EvidenceTrace";
import { RedditQuote } from "@/components/report/RedditQuote";
import { CitationHoverProvider } from "@/context/CitationHoverContext";
import type {
  AspectScore, ChatAPIResponse, CrimeRow, EmotionProfile as EmotionProfileType,
  EvidenceTrace as EvidenceTraceType, RedditHighlight, SuburbScore,
} from "@/types/api";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const MapPanel = dynamic(
  () => import("@/components/liveability/MapPanel").then((m) => m.MapPanel),
  { ssr: false }
);

// Minimal stub so MapPanel compiles — it only needs these props for locator mode
const EMPTY_WEIGHTS = { transport: 0, safety: 0, lifestyle: 0, afford: 0, proximity: 0 };

export default function SuburbReportPage() {
  const params = useParams();
  const suburbName = decodeURIComponent((params?.suburb as string) ?? "");

  const [payload, setPayload] = useState<ChatAPIResponse | null>(null);
  const [loading, setLoading]  = useState(true);

  useEffect(() => {
    if (!suburbName) return;
    setLoading(true);
    fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: `Tell me about ${suburbName}`, weights: { transport: 0.25, safety: 0.25, lifestyle: 0.25, affordability: 0.25, nightlife: 0.0, proximity: 0.0 } }),
    })
      .then((r) => r.ok ? r.json() as Promise<ChatAPIResponse> : Promise.reject())
      .then(setPayload)
      .catch(() => setPayload(null))
      .finally(() => setLoading(false));
  }, [suburbName]);

  const suburbScore: SuburbScore | undefined = payload?.suburb_scores?.find(
    (s) => s.name.toLowerCase() === suburbName.toLowerCase()
  );

  const aspects: AspectScore[]       = payload?.aspect_scores?.[suburbName]    ?? [];
  const emotions: EmotionProfileType | undefined = payload?.emotion_profile?.[suburbName];
  const reddit: RedditHighlight[]    = payload?.reddit_highlights?.[suburbName] ?? [];
  const crime: CrimeRow[]            = payload?.crime_breakdown?.[suburbName]   ?? [];
  const trace                        = payload?.quality?.evidence_trace_summary as EvidenceTraceType | string | null | undefined;

  const answer = payload?.answer ?? "";
  const router = payload?.router;

  const normalizeAnswerMarkdown = (text: string) => {
    let normalized = text.trim();
    normalized = normalized.replace(/\s+\*\s+/g, "\n- ");
    normalized = normalized.replace(/\s+>\s+/g, "\n\n> ");
    return normalized;
  };

  // Determine loved/concern from aspects
  const sorted    = [...aspects].sort((a, b) => b.pos - a.pos);
  const lovedItem = sorted[0];
  const concernItem = sorted[sorted.length - 1];

  const accentColor = "oklch(0.55 0.18 285)";

  const formatAspectPos = (pos: number | null | undefined) => {
    if (typeof pos !== "number") return "n/a";
    return pos.toFixed(2);
  };

  return (
    <CitationHoverProvider>
      <div className="min-h-screen bg-bg font-sans text-[13px] text-fg">
        {/* HEADER */}
        <div className="flex items-center gap-4 border-b border-border bg-bg px-6 py-4">
          <Link href="/" className="flex size-7 items-center justify-center rounded-md border border-border bg-bg text-fg transition hover:bg-bg-elev">
            <svg width="12" height="12" viewBox="0 0 14 14">
              <path d="M11 7H3m3-3-3 3 3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
          <div className="flex-1">
            <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
              Detailed report · single suburb
            </div>
            <div className="mt-0.5 text-[17px] font-semibold tracking-[-0.015em]">
              {suburbName}
              {suburbScore?.sa4 && (
                <span className="ml-2 font-normal text-fg-muted">· {suburbScore.sa4}</span>
              )}
            </div>
          </div>
          {router?.categories.map((c) => <CategoryChip key={c} kind={c} />)}
          <button
            type="button"
            onClick={() => window.print()}
            className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-bg px-3 py-[7px] text-[11.5px] font-medium text-fg transition hover:bg-bg-elev"
          >
            Export PDF
          </button>
        </div>

        {loading ? (
          <div className="flex h-96 items-center justify-center">
            <div className="flex items-center gap-2 font-mono text-[11px] text-fg-muted">
              <span className="size-4 animate-spin rounded-full border-2 border-border border-t-accent" />
              Loading report for {suburbName}…
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-[1280px] flex-col gap-5 p-6">
            {/* 1. ASSISTANT RESPONSE */}
            <SectionCard title="Assistant response" hint="echo of /api/chat answer">
              <div
                className="flex gap-4 rounded-lg p-4 text-[14px] leading-[1.65] tracking-[-0.005em]"
                style={{ background: "linear-gradient(180deg, oklch(0.99 0.01 285), oklch(0.992 0.002 250))" }}
              >
                <div className="w-1 shrink-0 self-stretch rounded-sm" style={{ background: accentColor }} />
                <div className="flex-1">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>,
                      li: ({ children }) => <li className="leading-snug">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold text-fg">{children}</strong>,
                      em: ({ children }) => <em className="italic text-fg-muted">{children}</em>,
                      blockquote: ({ children }) => (
                        <blockquote className="mt-2 border-l-2 border-border pl-3 text-fg-muted">
                          {children}
                        </blockquote>
                      ),
                    }}
                  >
                    {normalizeAnswerMarkdown(answer)}
                  </ReactMarkdown>
                </div>
              </div>
            </SectionCard>

            {/* 2. EXECUTIVE SUMMARY */}
            <SectionCard title="Executive summary" hint="weighted profile applied">
              {suburbScore ? (
                <div className="grid items-center gap-6" style={{ gridTemplateColumns: "200px 1fr 280px" }}>
                  <div className="flex flex-col items-center gap-2">
                    <ScoreGauge value={suburbScore.score} size={140} label="liveability" />
                    <div className="font-mono text-[10px] text-fg-muted">weighted · 0–100</div>
                  </div>
                  <div className="flex flex-col gap-3">
                    {([
                      { k: "transport",     v: suburbScore.transport,     w: 7 },
                      { k: "safety",        v: suburbScore.safety,        w: 8 },
                      { k: "lifestyle",     v: suburbScore.lifestyle,     w: 7 },
                      { k: "affordability", v: suburbScore.affordability, w: 2 },
                    ] as const).map(({ k, v, w }) => (
                      <div key={k} className="grid items-center gap-2.5" style={{ gridTemplateColumns: "100px 1fr 60px 60px" }}>
                        <div className="text-[12px] font-medium capitalize">{k}</div>
                        <Bar value={v} color={accentColor} height={6} />
                        <div className="font-mono text-[11.5px] font-semibold">{v}</div>
                        <div className="rounded border border-border bg-bg-elev text-center font-mono text-[10px] text-fg-muted px-1.5 py-px">
                          w·{w}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex flex-col gap-2">
                    {lovedItem && (
                      <Pill tone="pos" label="LOVED FOR" body={lovedItem.aspect}
                        sub={`${formatAspectPos(lovedItem.pos)} · ${lovedItem.mentions} mentions`} />
                    )}
                    {concernItem && (
                      <Pill tone="neg" label="CONCERN" body={concernItem.aspect}
                        sub={`${formatAspectPos(concernItem.pos)} · ${concernItem.mentions} mentions`} />
                    )}
                    {!lovedItem && (
                      <div className="rounded-lg border border-border bg-bg-elev p-3 font-mono text-[10.5px] text-fg-muted">
                        Aspect scores are not available yet.
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-border bg-bg-elev p-4 font-mono text-[10.5px] text-fg-muted">
                  Score summary is not available for {suburbName} yet.
                </div>
              )}
            </SectionCard>

            {/* 3. ASPECT RADAR + EMOTION */}
            <div className="grid gap-4" style={{ gridTemplateColumns: "1.3fr 1fr" }}>
              <SectionCard title="Aspect radar" hint={aspects.length > 0 ? `DeBERTa-v3 · ${aspects.reduce((a, b) => a + b.mentions, 0)} mentions` : undefined}>
                {aspects.length > 0 ? (
                  <AspectRadar data={aspects} accent={accentColor} size="lg" />
                ) : (
                  <div className="rounded-lg border border-border bg-bg-elev p-4 font-mono text-[10.5px] text-fg-muted">
                    Aspect radar is not available yet.
                  </div>
                )}
              </SectionCard>
              <SectionCard title="Emotion profile" hint="GoEmotions · averaged across posts">
                {emotions ? (
                  <EmotionProfile data={emotions} />
                ) : (
                  <div className="rounded-lg border border-border bg-bg-elev p-4 font-mono text-[10.5px] text-fg-muted">
                    Emotion profile is not available yet.
                  </div>
                )}
              </SectionCard>
            </div>

            {/* 4. CRIME + GIS */}
            <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <SectionCard title="Crime breakdown" hint={suburbScore?.sa4 ? `BOCSAR · ${suburbScore.sa4} SA4 · per 100k · 2024` : "BOCSAR"}>
                <CrimeBreakdown data={crime} crimeIdx={suburbScore?.crimeIdx} sa4={suburbScore?.sa4} />
              </SectionCard>
              <SectionCard title="GIS · facilities" hint="ArcGIS + OSM">
                {/* Real Leaflet map in locator mode */}
                <div className="overflow-hidden rounded-lg" style={{ height: 220 }}>
                  <MapPanel
                    suburbs={[]}
                    ranked={[]}
                    isLoading={false}
                    selectedSuburbId={null}
                    onSelectSuburb={() => {}}
                    layer="Liveability"
                    onLayerChange={() => {}}
                    weights={EMPTY_WEIGHTS}
                    activeSuburbs={[suburbName]}
                  />
                </div>
                {suburbScore ? (
                  <div className="mt-2.5 grid grid-cols-4 gap-2">
                    {([
                      { label: "cafes",       v: suburbScore.cafes       },
                      { label: "restaurants", v: suburbScore.restaurants },
                      { label: "parks",       v: suburbScore.parks       },
                      { label: "playgrounds", v: suburbScore.playgrounds },
                    ]).map(({ label, v }) => (
                      <div key={label} className="rounded-lg border border-border bg-bg p-2.5">
                        <div className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-fg-muted">{label}</div>
                        <div className="mt-0.5 font-mono text-lg font-semibold">{v}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-2 rounded-lg border border-border bg-bg-elev p-3 font-mono text-[10.5px] text-fg-muted">
                    Facilities counts are not available yet.
                  </div>
                )}
              </SectionCard>
            </div>

            {/* 5. REDDIT HIGHLIGHTS */}
            <SectionCard title="Reddit highlights" hint={reddit.length > 0 ? `${reddit.length} cited · permalinks preserved` : undefined}>
              {reddit.length > 0 ? (
                <div className="grid grid-cols-3 gap-2.5">
                  {reddit.map((q) => <RedditQuote key={q.id} q={q} variant="full" />)}
                </div>
              ) : (
                <div className="rounded-lg border border-border bg-bg-elev p-4 font-mono text-[10.5px] text-fg-muted">
                  Reddit highlights are not available yet.
                </div>
              )}
            </SectionCard>

            {/* 6. EVIDENCE TRACE */}
            <SectionCard title="Evidence trace" hint="auditable · pipeline + chunks">
              <EvidenceTrace trace={trace} />
            </SectionCard>
          </div>
        )}
      </div>
    </CitationHoverProvider>
  );
}
