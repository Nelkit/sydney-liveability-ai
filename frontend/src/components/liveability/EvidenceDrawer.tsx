"use client";

import { BookOpen } from "lucide-react";
import { Bar } from "@/components/ui/Bar";
import { SourceBadge } from "@/components/ui/SourceBadge";
import { useCitationHover } from "@/context/CitationHoverContext";
import type { Citation, EvidenceTrace } from "@/types/api";

type Props = {
  trace?: EvidenceTrace | string | null;
  allCitations?: Citation[];
};

const RETRIEVAL_SOURCES = [
  { label: "Reddit · MiniLM",    key: "reddit" },
  { label: "PostGIS facilities", key: "arcgis" },
  { label: "BOCSAR SA4",         key: "bocsar" },
  { label: "ArcGIS layers",      key: "osm"    },
] as const;

function isStructuredTrace(t: unknown): t is EvidenceTrace {
  return typeof t === "object" && t !== null && "router" in t && "specialists" in t;
}

export function EvidenceDrawer({ trace, allCitations = [] }: Props) {
  const { hoveredCite } = useCitationHover();
  const structured = isStructuredTrace(trace) ? trace : null;

  return (
    <div className="flex flex-col overflow-hidden border-l border-border" style={{ background: "radial-gradient(circle at 30% 18%, rgba(254,215,170,0.22), transparent 28%), linear-gradient(180deg,#eff2f8,#e9edf6)" }}>
      {/* Header */}
      <div className="flex h-[52px] items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2">
          <BookOpen size={14} strokeWidth={1.4} className="text-fg-muted" />
          <span className="text-[13.5px] font-semibold">Evidence trail</span>
        </div>
        <span className="rounded border border-border bg-bg-elev px-1.5 py-px font-mono text-[10px] text-fg-muted">
          auditable
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-3.5 overflow-auto p-3.5">
        {/* Pipeline section */}
        <DrawerSection title="Pipeline">
          {structured ? (
            <>
              <PipelineRow
                label="router"
                sub={structured.router.note || structured.router.model}
                ms={structured.router.ms}
              />
              {structured.specialists.map((s) => (
                <PipelineRow
                  key={s.id}
                  label={s.id}
                  sub={`${s.store} · ${s.retrieved} chunks`}
                  ms={s.ms}
                />
              ))}
            </>
          ) : trace && typeof trace === "string" ? (
            <div className="rounded-lg border border-border bg-bg-elev p-2.5 font-mono text-[10.5px] leading-[1.55] text-fg-muted whitespace-pre-wrap">
              {trace}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-bg-elev p-3 font-mono text-[10.5px] text-fg-muted">
              Evidence trace is not available for this response yet.
            </div>
          )}
        </DrawerSection>

        {/* Active citation detail */}
        <DrawerSection title={hoveredCite ? `Citation [${hoveredCite.n}]` : "Citations"}>
          {hoveredCite ? (
            <div
              className="flex flex-col gap-2 rounded-lg border p-2.5"
              style={{
                borderColor: "oklch(0.88 0.05 285)",
                background: "oklch(0.98 0.015 285)",
              }}
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <SourceBadge kind={hoveredCite.src} />
                {hoveredCite.suburbs.map((s) => (
                  <span
                    key={s}
                    className="rounded px-1.5 py-px font-mono text-[10px] text-white"
                    style={{ background: "oklch(0.55 0.18 285)" }}
                  >
                    @{s}
                  </span>
                ))}
              </div>
              <div className="text-xs leading-[1.5] text-fg">{hoveredCite.detail}</div>
              <div className="font-mono text-[10px] text-fg-muted">
                Hover ON · polygon highlighted on map
              </div>
            </div>
          ) : allCitations.length > 0 ? (
            allCitations.map((c) => (
              <button
                key={c.n}
                type="button"
                className="flex w-full cursor-pointer items-center gap-2 rounded-md border border-border bg-bg p-2 text-left transition hover:bg-bg-elev"
              >
                <span className="w-5 text-center font-mono text-[10.5px] text-fg-muted">
                  [{c.n}]
                </span>
                <SourceBadge kind={c.src} />
                <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[11.5px] text-fg">
                  {c.detail}
                </span>
              </button>
            ))
          ) : (
            <div className="font-mono text-[10.5px] text-fg-muted">
              Hover a [n] citation to see details here.
            </div>
          )}
        </DrawerSection>

        {/* Retrieval breakdown */}
        <DrawerSection title="Retrieval breakdown">
          {structured ? (
            structured.specialists.map((s) => (
              <RetrievalBar key={s.id} label={s.id} value={s.retrieved} max={20} />
            ))
          ) : (
            RETRIEVAL_SOURCES.map((s) => (
              <RetrievalBar key={s.key} label={s.label} value={0} max={20} placeholder />
            ))
          )}
        </DrawerSection>

        {/* Last updated */}
        <DrawerSection title="Source freshness">
          <div className="flex flex-col gap-1.5">
            {[
              { label: "Reddit", value: null, note: "last crawl date" },
              { label: "BOCSAR", value: "2024", note: "dataset year" },
              { label: "ArcGIS", value: "live", note: "real-time" },
            ].map(({ label, value, note }) =>
              value ? (
                <div key={label} className="flex items-center justify-between font-mono text-[10.5px]">
                  <span className="text-fg">{label}</span>
                  <span className="text-fg-muted">{value} · {note}</span>
                </div>
              ) : (
                <div key={label} className="flex items-center justify-between rounded border border-border bg-bg-elev p-2 font-mono text-[10px] text-fg-muted">
                  <span>{label}</span>
                  <span>last crawl date not available</span>
                </div>
              )
            )}
          </div>
        </DrawerSection>
      </div>
    </div>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
        {title}
      </div>
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  );
}

function PipelineRow({ label, sub, ms }: { label: string; sub: string; ms: number }) {
  return (
    <div className="flex items-center gap-2.5 rounded-md border border-border bg-bg-elev px-[10px] py-2">
      <span className="size-1.5 rounded-full bg-accent shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="font-mono text-[11.5px] font-medium">{label}</div>
        <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[10.5px] text-fg-muted">
          {sub}
        </div>
      </div>
      <div className="font-mono text-[10.5px] text-fg-muted shrink-0">{ms}ms</div>
    </div>
  );
}

function RetrievalBar({
  label, value, max, placeholder,
}: {
  label: string; value: number; max: number; placeholder?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-[11px]">
        <span className="text-fg">{label}</span>
        <span className="font-mono text-fg-muted">
          {placeholder ? "—" : `${value}/${max}`}
        </span>
      </div>
      <Bar value={placeholder ? 0 : value} max={max} height={4} />
    </div>
  );
}
