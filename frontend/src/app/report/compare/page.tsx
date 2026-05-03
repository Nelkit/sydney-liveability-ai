"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { CategoryChip } from "@/components/ui/CategoryChip";
import { DivergingBar } from "@/components/ui/Bar";
import { SectionCard } from "@/components/ui/SectionCard";
import { AspectRadar } from "@/components/report/AspectRadar";
import { RedditQuote } from "@/components/report/RedditQuote";
import { SuburbHero } from "@/components/report/SuburbHero";
import { CitationHoverProvider } from "@/context/CitationHoverContext";
import type {
  AspectScore, ChatAPIResponse, RedditHighlight, SuburbScore,
} from "@/types/api";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const ACCENT_A = "oklch(0.55 0.18 285)";
const ACCENT_B = "oklch(0.62 0.16 75)";

const DIMENSIONS = [
  { key: "transport" as const,     label: "Transport",     icon: "🚆" },
  { key: "safety" as const,        label: "Safety",        icon: "🛡" },
  { key: "lifestyle" as const,     label: "Lifestyle",     icon: "☕" },
  { key: "affordability" as const, label: "Affordability", icon: "$" },
] as const;

type CompareData = {
  a: SuburbScore;
  b: SuburbScore;
  aspectsA: AspectScore[];
  aspectsB: AspectScore[];
  redditA: RedditHighlight[];
  redditB: RedditHighlight[];
};

async function fetchForSuburb(name: string): Promise<ChatAPIResponse> {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: `Tell me about ${name}`, weights: { transport: 0.25, safety: 0.25, lifestyle: 0.25, affordability: 0.25, nightlife: 0.0, proximity: 0.0 } }),
  });
  if (!res.ok) throw new Error("API error");
  return res.json() as Promise<ChatAPIResponse>;
}

function ComparePage() {
  const params = useSearchParams();
  const suburbA = params?.get("a") ?? "";
  const suburbB = params?.get("b") ?? "";
  const [data, setData]     = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoverDim, setHoverDim] = useState<string | null>(null);
  const [layout, setLayout]   = useState<"split" | "rows">("split");

  useEffect(() => {
    if (!suburbA || !suburbB) return;
    setLoading(true);
    Promise.all([fetchForSuburb(suburbA), fetchForSuburb(suburbB)])
      .then(([pA, pB]) => {
        const scoreA = pA.suburb_scores?.find((s) => s.name.toLowerCase() === suburbA.toLowerCase());
        const scoreB = pB.suburb_scores?.find((s) => s.name.toLowerCase() === suburbB.toLowerCase());
        if (!scoreA || !scoreB) { setData(null); return; }
        setData({
          a: scoreA,
          b: scoreB,
          aspectsA: pA.aspect_scores?.[suburbA] ?? [],
          aspectsB: pB.aspect_scores?.[suburbB] ?? [],
          redditA:  pA.reddit_highlights?.[suburbA] ?? [],
          redditB:  pB.reddit_highlights?.[suburbB] ?? [],
        });
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [suburbA, suburbB]);

  if (!suburbA || !suburbB) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <div className="rounded-[10px] border border-border bg-bg-elev p-8 text-center">
          <div className="text-[17px] font-semibold">Comparator</div>
          <p className="mt-2 text-sm text-fg-muted">
            Add <code className="font-mono text-[12px]">?a=Newtown&b=Glebe</code> to the URL to compare two suburbs.
          </p>
          <Link href="/" className="mt-4 inline-block text-sm text-accent underline">← Back to chat</Link>
        </div>
      </div>
    );
  }

  const winner = data ? (data.a.score >= data.b.score ? suburbA : suburbB) : null;
  const delta  = data ? Math.abs(data.a.score - data.b.score) : 0;

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
          <div className="flex flex-1 items-center gap-3.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
              Detailed report · comparator
            </span>
            <div className="flex items-center gap-2.5 text-[17px] font-semibold tracking-[-0.015em]">
              <span style={{ color: ACCENT_A }}>{suburbA}</span>
              <span className="font-mono text-[13px] font-normal text-fg-muted">vs</span>
              <span style={{ color: ACCENT_B }}>{suburbB}</span>
            </div>
          </div>
          <CategoryChip kind="comparator" />
          <CategoryChip kind="sentiment" />
          <CategoryChip kind="gis" />
          <CategoryChip kind="crime" />

          {winner && (
            <div
              className="flex items-center gap-2 rounded-lg border px-3 py-1.5"
              style={{ background: "linear-gradient(180deg, oklch(0.97 0.025 285), oklch(0.99 0.01 285))", borderColor: "oklch(0.88 0.05 285)" }}
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.06em] text-fg-muted">verdict</span>
              <span className="text-[13px] font-semibold">{winner}</span>
              <span className="font-mono text-[11px] font-semibold text-accent">+{delta}</span>
            </div>
          )}

          {/* Layout toggle */}
          <div className="flex items-center gap-1 rounded-md border border-border p-[3px]">
            {(["split", "rows"] as const).map((l) => (
              <button key={l} type="button" onClick={() => setLayout(l)}
                className={`cursor-pointer rounded px-2 py-1 font-mono text-[10px] capitalize transition ${layout === l ? "bg-fg text-bg" : "text-fg-muted hover:text-fg"}`}>
                {l}
              </button>
            ))}
          </div>
        </div>

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
            <Link href="/" className="text-sm text-accent underline">← Back to chat</Link>
          </div>
        ) : layout === "split" ? (
          <SplitLayout
            suburbA={suburbA} suburbB={suburbB} data={data}
            hoverDim={hoverDim} setHoverDim={setHoverDim}
          />
        ) : (
          <RowsLayout suburbA={suburbA} suburbB={suburbB} data={data} />
        )}
      </div>
    </CitationHoverProvider>
  );
}

// ---------- Split layout ----------

function SplitLayout({
  suburbA, suburbB, data, hoverDim, setHoverDim,
}: {
  suburbA: string; suburbB: string; data: CompareData;
  hoverDim: string | null; setHoverDim: (d: string | null) => void;
}) {
  return (
    <div>
      {/* Heroes */}
      <div className="grid grid-cols-2">
        <SuburbHero name={suburbA} data={data.a} accent={ACCENT_A} side="left" />
        <SuburbHero name={suburbB} data={data.b} accent={ACCENT_B} side="right" />
      </div>

      {/* Head-to-head diverging bars */}
      <div className="border-t border-b border-border bg-bg-elev px-8 py-5">
        <div className="mb-3.5 flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
            head-to-head · weighted score 0–100
          </span>
          <div className="flex items-center gap-4 font-mono text-[11px] text-fg-muted">
            {[{ a: ACCENT_A, label: suburbA }, { a: ACCENT_B, label: suburbB }].map(({ a, label }) => (
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
                <div className="text-right font-mono text-[12px] font-semibold" style={{ color: winA ? ACCENT_A : "oklch(0.55 0.012 250)" }}>{va}</div>
                <div className="flex justify-end">
                  <div className="h-2.5 rounded-l" style={{ width: `${va}%`, background: winA ? ACCENT_A : "oklch(0.85 0.05 285)" }} />
                </div>
                <div className="flex items-center justify-center gap-2 text-[12px] font-medium">
                  <span>{d.icon}</span><span>{d.label}</span>
                </div>
                <div>
                  <div className="h-2.5 rounded-r" style={{ width: `${vb}%`, background: winB ? ACCENT_B : "oklch(0.88 0.04 75)" }} />
                </div>
                <div className="font-mono text-[12px] font-semibold" style={{ color: winB ? ACCENT_B : "oklch(0.55 0.012 250)" }}>{vb}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Aspect + Reddit per suburb */}
      <div className="grid grid-cols-2">
        <SuburbAspects name={suburbA} aspects={data.aspectsA} reddit={data.redditA} accent={ACCENT_A} side="left" />
        <SuburbAspects name={suburbB} aspects={data.aspectsB} reddit={data.redditB} accent={ACCENT_B} side="right" />
      </div>
    </div>
  );
}

function SuburbAspects({ name, aspects, reddit, accent, side }: {
  name: string; aspects: AspectScore[]; reddit: RedditHighlight[];
  accent: string; side: "left" | "right";
}) {
  return (
    <div className={`flex flex-col gap-4 p-6 ${side === "left" ? "border-r border-border" : ""}`}>
      <SectionCard title="Aspect sentiment · DeBERTa-v3" hint={aspects.length > 0 ? `${aspects.reduce((a, b) => a + b.mentions, 0)} mentions` : undefined}>
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
            {reddit.slice(0, 3).map((q) => <RedditQuote key={q.id} q={q} accent={accent} variant="compact" />)}
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

// ---------- Rows layout ----------

function RowsLayout({ suburbA, suburbB, data }: { suburbA: string; suburbB: string; data: CompareData }) {
  return (
    <div className="flex flex-col gap-3 p-6">
      {DIMENSIONS.map((d) => {
        const va = data.a[d.key as keyof SuburbScore] as number;
        const vb = data.b[d.key as keyof SuburbScore] as number;
        return (
          <div key={d.key} className="grid items-center gap-4 rounded-[10px] border border-border bg-bg p-4" style={{ gridTemplateColumns: "240px 1fr 1fr" }}>
            <div>
              <div className="text-[14px] font-semibold tracking-[-0.01em]">{d.label}</div>
            </div>
            <DimSide name={suburbA} value={va} accent={ACCENT_A} winning={va >= vb} />
            <DimSide name={suburbB} value={vb} accent={ACCENT_B} winning={vb >= va} />
          </div>
        );
      })}
    </div>
  );
}

function DimSide({ name, value, accent, winning }: { name: string; value: number; accent: string; winning: boolean }) {
  return (
    <div className="rounded-lg p-3" style={{
      background: winning ? `color-mix(in oklch, ${accent} 8%, oklch(0.992 0.002 250))` : "oklch(0.975 0.004 250)",
      border: `1px solid ${winning ? accent : "oklch(0.92 0.005 250)"}`,
    }}>
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium">{name}</span>
        <span className="font-mono text-[14px] font-semibold" style={{ color: winning ? accent : "oklch(0.18 0.01 250)" }}>{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-border">
        <div className="h-full rounded-full" style={{ width: `${value}%`, background: accent }} />
      </div>
    </div>
  );
}

// ---------- Export with Suspense ----------

export default function ComparatorPage() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center bg-bg font-mono text-[11px] text-fg-muted">Loading comparator…</div>}>
      <ComparePage />
    </Suspense>
  );
}
