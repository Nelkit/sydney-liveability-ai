"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { CategoryChip } from "@/components/ui/CategoryChip";
import { InlineCitations } from "@/components/ui/InlineCitations";
import { Pill } from "@/components/ui/Pill";
import { ScoreGauge } from "@/components/ui/ScoreGauge";
import { SectionCard } from "@/components/ui/SectionCard";
import { Bar } from "@/components/ui/Bar";
import { AspectRadar } from "@/components/report/AspectRadar";
import { CrimeBreakdown } from "@/components/report/CrimeBreakdown";
import { EmotionProfile } from "@/components/report/EmotionProfile";
import { EvidenceTrace } from "@/components/report/EvidenceTrace";
import { RedditQuote } from "@/components/report/RedditQuote";
import { SuburbHero } from "@/components/report/SuburbHero";
import { CitationHoverProvider } from "@/context/CitationHoverContext";
import type {
  AspectScore,
  ChatAPIResponse,
  Citation,
  CrimeRow,
  EmotionProfile as EmotionProfileType,
  EvidenceTrace as EvidenceTraceType,
  RedditHighlight,
  SourceKind,
  SuburbScore,
} from "@/types/api";

// ---------- citation helpers ----------

const SOURCE_KIND_LIST: SourceKind[] = ["reddit", "bocsar", "arcgis", "osm", "tfnsw", "pdf"];

function isSourceKind(v: unknown): v is SourceKind {
  return typeof v === "string" && SOURCE_KIND_LIST.includes(v as SourceKind);
}

type SourceObject = { source?: SourceKind; suburb?: string; text?: string };

function isSourceObject(v: unknown): v is SourceObject {
  return typeof v === "object" && v !== null && ("source" in v || "suburb" in v || "text" in v);
}

function extractCitations(payload: ChatAPIResponse, suburbs: string[]): Citation[] {
  const raw: unknown[] = Array.isArray(payload.sources) ? (payload.sources as unknown[]) : [];
  if (!raw.length) return [];
  const citations: Citation[] = [];
  let n = 1;
  raw.forEach((item) => {
    if (isSourceKind(item)) {
      citations.push({ n: n++, src: item, suburbs, detail: `${suburbs.join(", ")} · ${item}` });
      return;
    }
    if (isSourceObject(item)) {
      const kind = isSourceKind(item.source) ? item.source : null;
      if (!kind) return;
      const citeSuburbs = item.suburb ? [item.suburb] : suburbs;
      const detail = item.text ? item.text : `${citeSuburbs.join(", ")} · ${kind}`;
      citations.push({ n: n++, src: kind, suburbs: citeSuburbs, detail });
    }
  });
  return citations;
}

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const EMPTY_WEIGHTS = { transport: 0, safety: 0, lifestyle: 0, afford: 0, proximity: 0 };

const MapPanel = dynamic(
  () => import("@/components/liveability/MapPanel").then((m) => m.MapPanel),
  { ssr: false }
);

// ---------- types ----------

export type ReportModalProps = {
  mode: "single" | "compare";
  suburbs: string[];
  question?: string;
  onClose: () => void;
  payload?: ChatAPIResponse;
  payloads?: Record<string, ChatAPIResponse>;
};

// ---------- close button ----------

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button
      type="button"
      onClick={onClose}
      aria-label="Close"
      className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border bg-bg text-fg hover:bg-bg-elev cursor-pointer transition"
    >
      <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden>
        <path
          d="M2 2l10 10M12 2 2 12"
          stroke="currentColor"
          strokeWidth="1.5"
          fill="none"
          strokeLinecap="round"
        />
      </svg>
    </button>
  );
}

// ==========================================================================
// SINGLE SUBURB REPORT
// ==========================================================================

const ACCENT_SINGLE = "oklch(0.55 0.18 285)";

function SingleReport({
  suburbName,
  question,
  onClose,
  initialPayload,
}: {
  suburbName: string;
  question?: string;
  onClose: () => void;
  initialPayload?: ChatAPIResponse;
}) {
  const [payload, setPayload] = useState<ChatAPIResponse | null>(initialPayload ?? null);
  const [loading, setLoading] = useState(!initialPayload);

  useEffect(() => {
    if (initialPayload || !suburbName) return;
    setLoading(true);
    fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: `Tell me about ${suburbName}`,
        weights: { transport: 0.25, safety: 0.25, lifestyle: 0.25, affordability: 0.25, nightlife: 0.0, proximity: 0.0 },
      }),
    })
      .then((r) => (r.ok ? (r.json() as Promise<ChatAPIResponse>) : Promise.reject()))
      .then(setPayload)
      .catch(() => setPayload(null))
      .finally(() => setLoading(false));
  }, [suburbName, initialPayload]);

  const suburbScore: SuburbScore | undefined = payload?.suburb_scores?.find(
    (s) => s.name.toLowerCase() === suburbName.toLowerCase()
  );

  const aspects: AspectScore[] = payload?.aspect_scores?.[suburbName] ?? [];
  const emotions: EmotionProfileType | undefined = payload?.emotion_profile?.[suburbName];
  const reddit: RedditHighlight[] = payload?.reddit_highlights?.[suburbName] ?? [];
  const crime: CrimeRow[] = payload?.crime_breakdown?.[suburbName] ?? [];
  const trace = payload?.quality?.evidence_trace_summary as EvidenceTraceType | string | null | undefined;

  const rawAnswer = payload?.answer ?? "";
  // Strip the trailing blockquote CTA ("> ...") — it's a chat teaser, not report content
  const answer = rawAnswer.replace(/\n>\s+[^\n]*$/s, "").trimEnd();
  const router = payload?.router;

  const citations = payload ? extractCitations(payload, [suburbName]) : [];

  const sorted = [...aspects].sort((a, b) => b.pos - a.pos);
  const lovedItem = sorted[0];
  const concernItem = sorted[sorted.length - 1];

  const formatAspectPos = (pos: number | null | undefined) => {
    if (typeof pos !== "number") return "n/a";
    return `${Math.round(pos * 100)}%`;
  };

  return (
    <>
      {/* HEADER */}
      <div className="flex flex-col gap-3 border-b border-border bg-bg px-6 py-4 shrink-0 md:flex-row md:items-center md:gap-4">
        <div className="flex items-start justify-between gap-4 md:contents">
          <div className="flex-1">
            <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
              Detailed report · single suburb
            </div>
            <div className="mt-0.5 text-[17px] font-semibold tracking-[-0.015em]">
              {suburbName}
              {suburbScore?.sa4 && suburbScore.sa4 !== "N/A" && (
                <span className="ml-2 font-normal text-fg-muted">· {suburbScore.sa4}</span>
              )}
            </div>
            {question && (
              <div className="mt-1 flex items-center gap-1.5">
                <span className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-fg-muted">q</span>
                <span className="font-mono text-[11px] text-fg-muted italic truncate max-w-[420px]">
                  {question}
                </span>
              </div>
            )}
          </div>
          <div className="shrink-0 md:hidden">
            <CloseButton onClose={onClose} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 md:contents">
          {router?.categories.map((c) => <CategoryChip key={c} kind={c} />)}
          <button
            type="button"
            onClick={() => window.print()}
            className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-bg px-3 py-[7px] text-[11.5px] font-medium text-fg transition hover:bg-bg-elev"
          >
            Export PDF
          </button>
        </div>
        <div className="hidden md:block">
          <CloseButton onClose={onClose} />
        </div>
      </div>

      {/* CONTENT */}
      <div className="flex-1 overflow-y-auto">
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
                style={{
                  background:
                    "linear-gradient(180deg, oklch(0.99 0.01 285), oklch(0.992 0.002 250))",
                }}
              >
                <div
                  className="w-1 shrink-0 self-stretch rounded-sm"
                  style={{ background: ACCENT_SINGLE }}
                />
                <div className="flex flex-col min-w-0 flex-1">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>,
                      li: ({ children }) => <li className="leading-snug">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      em: ({ children }) => <em className="italic opacity-75">{children}</em>,
                    }}
                  >
                    {answer}
                  </ReactMarkdown>
                  <InlineCitations citations={citations} />
                </div>
              </div>
            </SectionCard>

            {/* 2. EXECUTIVE SUMMARY */}
            <SectionCard title="Executive summary" hint="weighted liveability scores · 0–100">
              {suburbScore ? (
                <div
                  className="grid grid-cols-1 md:grid-cols-[200px_1fr_280px] items-center gap-6"
                >
                  <div className="flex flex-col items-center gap-2">
                    <ScoreGauge value={suburbScore.score} size={140} label="liveability" />
                    <div className="font-mono text-[10px] text-fg-muted">composite · 0–100</div>
                  </div>
                  <div className="flex flex-col gap-3">
                    <div className="mb-0.5 font-mono text-[9.5px] uppercase tracking-[0.06em] text-fg-muted">
                      Liveability dimensions · score 0–100 · weight %
                    </div>
                    {(
                      [
                        { k: "transport", v: suburbScore.transport, w: 7 },
                        { k: "safety", v: suburbScore.safety, w: 8 },
                        { k: "lifestyle", v: suburbScore.lifestyle, w: 7 },
                        { k: "affordability", v: suburbScore.affordability, w: 2 },
                      ] as const
                    ).map(({ k, v, w }) => (
                      <div
                        key={k}
                        className="grid items-center gap-2.5"
                        style={{ gridTemplateColumns: "100px 1fr 60px 60px" }}
                      >
                        <div className="text-[12px] font-medium capitalize">{k}</div>
                        <Bar value={v} color={ACCENT_SINGLE} height={6} />
                        <div className="font-mono text-[11.5px] font-semibold">{v}</div>
                        <div className="rounded border border-border bg-bg-elev text-center font-mono text-[10px] text-fg-muted px-1.5 py-px">
                          {w * 10}%
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex w-full overflow-hidden flex-col gap-2">
                    {lovedItem && (
                      <Pill
                        tone="pos"
                        label="LOVED FOR"
                        body={lovedItem.aspect}
                        sub={`Reddit sentiment ${formatAspectPos(lovedItem.pos)} · ${lovedItem.mentions} mentions`}
                      />
                    )}
                    {concernItem && (
                      <Pill
                        tone="neg"
                        label="CONCERN"
                        body={concernItem.aspect}
                        sub={`Reddit sentiment ${formatAspectPos(concernItem.pos)} · ${concernItem.mentions} mentions`}
                      />
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
            <div className="grid grid-cols-1 md:grid-cols-[1.3fr_1fr] gap-4">
              <SectionCard
                title="Reddit sentiment · by topic"
                hint={
                  aspects.length > 0
                    ? `DeBERTa-v3 NLP · ${aspects.reduce((a, b) => a + b.mentions, 0)} Reddit mentions`
                    : undefined
                }
              >
                {aspects.length > 0 ? (
                  <AspectRadar data={aspects} accent={ACCENT_SINGLE} size="lg" />
                ) : (
                  <div className="rounded-lg border border-border bg-bg-elev p-4 font-mono text-[10.5px] text-fg-muted">
                    Aspect radar is not available yet.
                  </div>
                )}
              </SectionCard>
              <SectionCard
                title="Resident emotion · Reddit posts"
                hint="GoEmotions classifier · probability distribution"
              >
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
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <SectionCard
                title="Crime breakdown"
                hint={
                  suburbScore?.sa4 && suburbScore.sa4 !== "N/A"
                    ? `BOCSAR · ${suburbScore.sa4} SA4 · per 100k · 2024`
                    : "BOCSAR"
                }
              >
                <CrimeBreakdown
                  data={crime}
                  crimeIdx={suburbScore?.crimeIdx}
                  sa4={suburbScore?.sa4}
                />
              </SectionCard>
              <SectionCard title="GIS · facilities" hint="ArcGIS + OSM">
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
                    hideRanking
                  />
                </div>
                {suburbScore ? (
                  <div className="mt-2.5 grid grid-cols-4 gap-2">
                    {(
                      [
                        { label: "cafes", v: suburbScore.cafes },
                        { label: "restaurants", v: suburbScore.restaurants },
                        { label: "parks", v: suburbScore.parks },
                        { label: "playgrounds", v: suburbScore.playgrounds },
                      ] as const
                    ).map(({ label, v }) => (
                      <div key={label} className="rounded-lg border border-border bg-bg p-2.5">
                        <div className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-fg-muted">
                          {label}
                        </div>
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
            <SectionCard
              title="Reddit highlights"
              hint={
                reddit.length > 0 ? `${reddit.length} cited · permalinks preserved` : undefined
              }
            >
              {reddit.length > 0 ? (
                <div className="grid grid-cols-1 gap-2.5 md:grid-cols-3">
                  {reddit.map((q) => (
                    <RedditQuote key={q.id} q={q} variant="full" />
                  ))}
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
    </>
  );
}

// ==========================================================================
// COMPARATOR REPORT
// ==========================================================================

const ACCENT_A = "oklch(0.55 0.18 285)";
const ACCENT_B = "oklch(0.62 0.16 75)";

const DIMENSIONS = [
  { key: "transport" as const, label: "Transport", icon: "🚆" },
  { key: "safety" as const, label: "Safety", icon: "🛡" },
  { key: "lifestyle" as const, label: "Lifestyle", icon: "☕" },
  { key: "affordability" as const, label: "Affordability", icon: "$" },
] as const;

type CompareData = {
  a: SuburbScore;
  b: SuburbScore;
  aspectsA: AspectScore[];
  aspectsB: AspectScore[];
  redditA: RedditHighlight[];
  redditB: RedditHighlight[];
  answer: string;
  citations: Citation[];
};

async function fetchForSuburb(name: string): Promise<ChatAPIResponse> {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: `Tell me about ${name}`,
      weights: { transport: 0.25, safety: 0.25, lifestyle: 0.25, affordability: 0.25, nightlife: 0.0, proximity: 0.0 },
    }),
  });
  if (!res.ok) throw new Error("API error");
  return res.json() as Promise<ChatAPIResponse>;
}

function SuburbAspectsPanel({
  name,
  aspects,
  reddit,
  accent,
  side,
}: {
  name: string;
  aspects: AspectScore[];
  reddit: RedditHighlight[];
  accent: string;
  side: "left" | "right";
}) {
  return (
    <div className={`flex flex-col gap-4 p-6 ${side === "left" ? "border-r border-border" : ""}`}>
      <SectionCard
        title="Aspect sentiment · DeBERTa-v3"
        hint={
          aspects.length > 0
            ? `${aspects.reduce((a, b) => a + b.mentions, 0)} mentions`
            : undefined
        }
      >
        {aspects.length > 0 ? (
          <AspectRadar data={aspects} accent={accent} size="sm" />
        ) : (
          <div className="rounded-lg border border-border bg-bg-elev p-3 font-mono text-[10.5px] text-fg-muted">
            Aspect sentiment is not available for {name} yet.
          </div>
        )}
      </SectionCard>
      <div>
        <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
          Reddit highlights
        </div>
        {reddit.length > 0 ? (
          <div className="flex flex-col gap-2">
            {reddit.slice(0, 3).map((q) => (
              <RedditQuote key={q.id} q={q} accent={accent} variant="compact" />
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-bg-elev p-3 font-mono text-[10.5px] text-fg-muted">
            Reddit highlights are not available for {name} yet.
          </div>
        )}
      </div>
    </div>
  );
}

function SplitLayout({
  suburbA,
  suburbB,
  data,
  hoverDim,
  setHoverDim,
  mobileTab,
}: {
  suburbA: string;
  suburbB: string;
  data: CompareData;
  hoverDim: string | null;
  setHoverDim: (d: string | null) => void;
  mobileTab: "a" | "b";
}) {
  return (
    <div>
      {/* Heroes */}
      <div className="grid grid-cols-1 md:grid-cols-2">
        <div className={mobileTab === "a" ? "block" : "hidden md:block"}>
          <SuburbHero name={suburbA} data={data.a} accent={ACCENT_A} side="left" />
        </div>
        <div className={mobileTab === "b" ? "block" : "hidden md:block"}>
          <SuburbHero name={suburbB} data={data.b} accent={ACCENT_B} side="right" />
        </div>
      </div>

      {/* Head-to-head diverging bars */}
      <div className="border-t border-b border-border bg-bg-elev px-8 py-5">
        <div className="mb-3.5 flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
            head-to-head · weighted score 0–100
          </span>
          <div className="flex items-center gap-4 font-mono text-[11px] text-fg-muted">
            {[
              { a: ACCENT_A, label: suburbA },
              { a: ACCENT_B, label: suburbB },
            ].map(({ a, label }) => (
              <span key={label} className="flex items-center gap-1.5">
                <span className="size-2 rounded-sm" style={{ background: a }} />
                {label}
              </span>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-2.5">
          {DIMENSIONS.map((d) => {
            const va = data.a[d.key as keyof SuburbScore] as number;
            const vb = data.b[d.key as keyof SuburbScore] as number;
            const winA = va > vb;
            const winB = vb > va;
            return (
              <div
                key={d.key}
                onMouseEnter={() => setHoverDim(d.key)}
                onMouseLeave={() => setHoverDim(null)}
                className={`grid items-center gap-3 rounded-lg px-2.5 py-2 transition ${hoverDim === d.key ? "bg-bg" : "bg-transparent"}`}
                style={{ gridTemplateColumns: "60px 1fr 120px 1fr 60px", cursor: "default" }}
              >
                <div
                  className="text-right font-mono text-[12px] font-semibold"
                  style={{ color: winA ? ACCENT_A : "oklch(0.55 0.012 250)" }}
                >
                  {va}
                </div>
                <div className="flex justify-end">
                  <div
                    className="h-2.5 rounded-l"
                    style={{
                      width: `${va}%`,
                      background: winA ? ACCENT_A : "oklch(0.85 0.05 285)",
                    }}
                  />
                </div>
                <div className="flex items-center justify-center gap-2 text-[12px] font-medium">
                  <span>{d.icon}</span>
                  <span>{d.label}</span>
                </div>
                <div>
                  <div
                    className="h-2.5 rounded-r"
                    style={{
                      width: `${vb}%`,
                      background: winB ? ACCENT_B : "oklch(0.88 0.04 75)",
                    }}
                  />
                </div>
                <div
                  className="font-mono text-[12px] font-semibold"
                  style={{ color: winB ? ACCENT_B : "oklch(0.55 0.012 250)" }}
                >
                  {vb}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Aspect + Reddit per suburb */}
      <div className="grid grid-cols-1 md:grid-cols-2">
        <div className={mobileTab === "a" ? "block" : "hidden md:block"}>
          <SuburbAspectsPanel
            name={suburbA}
            aspects={data.aspectsA}
            reddit={data.redditA}
            accent={ACCENT_A}
            side="left"
          />
        </div>
        <div className={mobileTab === "b" ? "block" : "hidden md:block"}>
          <SuburbAspectsPanel
            name={suburbB}
            aspects={data.aspectsB}
            reddit={data.redditB}
            accent={ACCENT_B}
            side="right"
          />
        </div>
      </div>
    </div>
  );
}

function DimSide({
  name,
  value,
  accent,
  winning,
}: {
  name: string;
  value: number;
  accent: string;
  winning: boolean;
}) {
  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: winning
          ? `color-mix(in oklch, ${accent} 8%, oklch(0.992 0.002 250))`
          : "oklch(0.975 0.004 250)",
        border: `1px solid ${winning ? accent : "oklch(0.92 0.005 250)"}`,
      }}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium">{name}</span>
        <span
          className="font-mono text-[14px] font-semibold"
          style={{ color: winning ? accent : "oklch(0.18 0.01 250)" }}
        >
          {value}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full"
          style={{ width: `${value}%`, background: accent }}
        />
      </div>
    </div>
  );
}

function RowsLayout({
  suburbA,
  suburbB,
  data,
  mobileTab,
}: {
  suburbA: string;
  suburbB: string;
  data: CompareData;
  mobileTab: "a" | "b";
}) {
  return (
    <div className="flex flex-col gap-3 p-6">
      {DIMENSIONS.map((d) => {
        const va = data.a[d.key as keyof SuburbScore] as number;
        const vb = data.b[d.key as keyof SuburbScore] as number;
        return (
          <div
            key={d.key}
            className="grid items-center gap-4 rounded-[10px] border border-border bg-bg p-4 grid-cols-[1fr] md:grid-cols-[240px_1fr_1fr]"
          >
            <div>
              <div className="text-[14px] font-semibold tracking-[-0.01em]">{d.label}</div>
            </div>
            <div className={mobileTab === "a" ? "block" : "hidden md:block"}>
              <DimSide name={suburbA} value={va} accent={ACCENT_A} winning={va >= vb} />
            </div>
            <div className={mobileTab === "b" ? "block" : "hidden md:block"}>
              <DimSide name={suburbB} value={vb} accent={ACCENT_B} winning={vb >= va} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CompareReport({
  suburbA,
  suburbB,
  question,
  onClose,
  payloads,
}: {
  suburbA: string;
  suburbB: string;
  question?: string;
  onClose: () => void;
  payloads?: Record<string, ChatAPIResponse>;
}) {
  const [data, setData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoverDim, setHoverDim] = useState<string | null>(null);
  const [layout, setLayout] = useState<"split" | "rows">("split");
  const [mobileTab, setMobileTab] = useState<"a" | "b">("a");

  useEffect(() => {
    if (!suburbA || !suburbB) return;
    setLoading(true);
    const cachedA = payloads?.[suburbA.toLowerCase()];
    const cachedB = payloads?.[suburbB.toLowerCase()];
    Promise.all([
      cachedA ? Promise.resolve(cachedA) : fetchForSuburb(suburbA),
      cachedB ? Promise.resolve(cachedB) : fetchForSuburb(suburbB),
    ])
      .then(([pA, pB]) => {
        const scoreA = pA.suburb_scores?.find(
          (s) => s.name.toLowerCase() === suburbA.toLowerCase()
        );
        const scoreB = pB.suburb_scores?.find(
          (s) => s.name.toLowerCase() === suburbB.toLowerCase()
        );
        if (!scoreA || !scoreB) {
          setData(null);
          return;
        }
        const answerA = pA.answer ?? "";
        const answerB = pB.answer ?? "";
        const winnerPayload = answerA.length >= answerB.length ? pA : pB;
        const winnerSuburbs = answerA.length >= answerB.length ? [suburbA] : [suburbB];
        setData({
          a: scoreA,
          b: scoreB,
          aspectsA: pA.aspect_scores?.[suburbA] ?? [],
          aspectsB: pB.aspect_scores?.[suburbB] ?? [],
          redditA: pA.reddit_highlights?.[suburbA] ?? [],
          redditB: pB.reddit_highlights?.[suburbB] ?? [],
          answer: answerA.length >= answerB.length ? answerA : answerB,
          citations: extractCitations(winnerPayload, winnerSuburbs),
        });
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [suburbA, suburbB, payloads]);

  const winner = data ? (data.a.score >= data.b.score ? suburbA : suburbB) : null;
  const delta = data ? Math.abs(data.a.score - data.b.score).toFixed(2) : 0;

  return (
    <>
      {/* HEADER */}
      <div className="flex flex-col gap-3 border-b border-border bg-bg px-6 py-4 shrink-0 md:flex-row md:items-center md:gap-4">
        {/* Row 1: title + suburbs + close (mobile) */}
        <div className="flex items-start justify-between gap-4 md:contents">
          <div className="flex flex-1 flex-col gap-0.5">
            <div className="flex flex-wrap items-center gap-3.5">
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
                Detailed report · comparator
              </span>
              <div className="flex items-center gap-2.5 text-[17px] font-semibold tracking-[-0.015em]">
                <span style={{ color: ACCENT_A }}>{suburbA}</span>
                <span className="font-mono text-[13px] font-normal text-fg-muted">vs</span>
                <span style={{ color: ACCENT_B }}>{suburbB}</span>
              </div>
            </div>
            {question && (
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-fg-muted">q</span>
                <span className="font-mono text-[11px] text-fg-muted italic truncate max-w-[480px]">
                  {question}
                </span>
              </div>
            )}
          </div>
          <div className="shrink-0 md:hidden">
            <CloseButton onClose={onClose} />
          </div>
        </div>

        {/* Row 2: chips + verdict + toggle */}
        <div className="flex flex-wrap items-center gap-2 md:contents">
          <CategoryChip kind="comparator" />
          <CategoryChip kind="sentiment" />
          <CategoryChip kind="gis" />
          <CategoryChip kind="crime" />

          {winner && (
            <div
              className="flex items-center gap-2 rounded-lg border px-3 py-1.5"
              style={{
                background:
                  "linear-gradient(180deg, oklch(0.97 0.025 285), oklch(0.99 0.01 285))",
                borderColor: "oklch(0.88 0.05 285)",
              }}
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.06em] text-fg-muted">
                verdict
              </span>
              <span className="text-[13px] font-semibold">{winner}</span>
              <span className="font-mono text-[11px] font-semibold text-accent">+{delta}</span>
            </div>
          )}

          <div className="flex items-center gap-1 rounded-md border border-border p-[3px]">
            {(["split", "rows"] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLayout(l)}
                className={`cursor-pointer rounded px-2 py-1 font-mono text-[10px] capitalize transition ${layout === l ? "bg-fg text-bg" : "text-fg-muted hover:text-fg"}`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        <div className="hidden md:block">
          <CloseButton onClose={onClose} />
        </div>
      </div>

      {/* CONTENT */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-96 items-center justify-center">
            <div className="flex items-center gap-2 font-mono text-[11px] text-fg-muted">
              <span className="size-4 animate-spin rounded-full border-2 border-border border-t-accent" />
              Loading comparison…
            </div>
          </div>
        ) : !data ? (
          <div className="flex flex-col items-center gap-3 p-12">
            <div className="rounded-lg border border-border bg-bg-elev p-6 font-mono text-[10.5px] text-fg-muted">
              Comparator data is not available for {suburbA} and/or {suburbB} yet.
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-[1280px] flex-col gap-5 p-6">
            {data.answer && (
              <SectionCard title="Assistant response" hint="synthesised comparison">
                <div
                  className="flex gap-4 rounded-lg p-4 text-[14px] leading-[1.65] tracking-[-0.005em]"
                  style={{ background: "linear-gradient(180deg, oklch(0.99 0.01 285), oklch(0.992 0.002 250))" }}
                >
                  <div className="w-1 shrink-0 self-stretch rounded-sm" style={{ background: ACCENT_A }} />
                  <div className="flex flex-col min-w-0 flex-1">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                        ul: ({ children }) => <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>,
                        li: ({ children }) => <li className="leading-snug">{children}</li>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        em: ({ children }) => <em className="italic opacity-75">{children}</em>,
                      }}
                    >
                      {data.answer.replace(/\n>\s+[^\n]*$/s, "").trimEnd()}
                    </ReactMarkdown>
                    <InlineCitations citations={data.citations} />
                  </div>
                </div>
              </SectionCard>
            )}

            {/* Mobile tab switcher */}
            <div className="flex rounded-lg border border-border p-1 md:hidden">
              {([{ id: "a", name: suburbA, accent: ACCENT_A }, { id: "b", name: suburbB, accent: ACCENT_B }] as const).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setMobileTab(t.id)}
                  className="flex-1 rounded-md py-2 font-mono text-[11px] font-semibold transition"
                  style={
                    mobileTab === t.id
                      ? { background: t.accent, color: "oklch(0.99 0.005 250)" }
                      : { color: "oklch(0.55 0.012 250)" }
                  }
                >
                  {t.name}
                </button>
              ))}
            </div>

            {layout === "split" ? (
              <SplitLayout
                suburbA={suburbA}
                suburbB={suburbB}
                data={data}
                hoverDim={hoverDim}
                setHoverDim={setHoverDim}
                mobileTab={mobileTab}
              />
            ) : (
              <RowsLayout suburbA={suburbA} suburbB={suburbB} data={data} mobileTab={mobileTab} />
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ==========================================================================
// MODAL SHELL
// ==========================================================================

export function ReportModal({ mode, suburbs, question, onClose, payload, payloads }: ReportModalProps) {
  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <CitationHoverProvider>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[900] bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="fixed inset-0 z-[901] pointer-events-none"
        role="dialog"
        aria-modal="true"
      >
        <div
          className="absolute inset-x-0 inset-y-0 md:inset-x-[5%] md:inset-y-[3%] pointer-events-auto rounded-xl border border-border shadow-floatLg overflow-hidden flex flex-col font-sans text-[13px] text-fg"
          style={{ background: "radial-gradient(circle at 30% 18%, rgba(254,215,170,0.22), transparent 28%), linear-gradient(180deg,#eff2f8,#e9edf6)" }}
          onClick={(e) => e.stopPropagation()}
        >
          {mode === "single" ? (
            <SingleReport suburbName={suburbs[0] ?? ""} question={question} onClose={onClose} initialPayload={payload} />
          ) : (
            <CompareReport
              suburbA={suburbs[0] ?? ""}
              suburbB={suburbs[1] ?? ""}
              question={question}
              onClose={onClose}
              payloads={payloads}
            />
          )}
        </div>
      </div>
    </CitationHoverProvider>
  );
}
