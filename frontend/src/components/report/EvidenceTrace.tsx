import { Bar } from "@/components/ui/Bar";
import type { EvidenceTrace as EvidenceTraceType } from "@/types/api";

const RETRIEVAL_LABELS = [
  { label: "Reddit · MiniLM",    key: "reddit"    },
  { label: "PostGIS facilities", key: "arcgis"    },
  { label: "BOCSAR SA4",         key: "bocsar"    },
  { label: "OSM",                key: "osm"       },
  { label: "GTFS Transport",     key: "transport" },
];

type Props = {
  trace?: EvidenceTraceType | string | null;
};

function isStructured(t: unknown): t is EvidenceTraceType {
  return typeof t === "object" && t !== null && "router" in t && "specialists" in t;
}

export function EvidenceTrace({ trace }: Props) {
  const structured = isStructured(trace) ? trace : null;

  return (
    <div className="flex flex-col gap-3">
      {/* Horizontal pipeline */}
      <div className="flex flex-col gap-2 md:flex-row md:items-stretch">
        {structured ? (
          <>
            <PipelineNode label="router" sub={structured.router.note || structured.router.model} ms={structured.router.ms} position="first" />
            {structured.specialists.map((s, i) => (
              <PipelineNode key={s.id} label={s.id} sub={`${s.store} · ${s.retrieved} chunks`} ms={s.ms}
                position={i === structured.specialists.length - 1 ? "last" : "middle"} />
            ))}
          </>
        ) : (
          <div className="w-full rounded-lg border border-border bg-bg-elev p-3 font-mono text-[10.5px] text-fg-muted">
            Evidence trace is not available for this response yet.
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {/* Retrieval breakdown */}
        <div>
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">retrieval</div>
          {(structured
            ? structured.specialists.map((s) => ({ label: s.id, value: s.retrieved }))
            : RETRIEVAL_LABELS.map(({ label }) => ({ label, value: 0 }))
          ).map(({ label, value }) => (
            <div key={label} className="mb-2 flex flex-col gap-1">
              <div className="flex justify-between text-[11px]">
                <span>{label}</span>
                <span className="font-mono text-fg-muted">{structured ? `${value}/20` : "—"}</span>
              </div>
              <Bar value={structured ? value : 0} max={20} height={4} />
            </div>
          ))}
        </div>

        {/* Summary box */}
        <div className="rounded-lg border border-border bg-bg-elev p-3 font-mono text-[11px] leading-[1.7] text-fg">
          {structured ? (
            <>
              <div className="mb-1 text-fg-muted">quality.evidence_trace_summary</div>
              <div>
                route:{" "}
                <span style={{ color: "oklch(0.45 0.14 285)" }}>
                  {structured.specialists.map((s) => s.id).join(" · ")}
                </span>
              </div>
              <div>chunks_total: {structured.specialists.reduce((a, s) => a + s.retrieved, 0)} · stores: {new Set(structured.specialists.map((s) => s.store)).size}</div>
              <div>latency_ms: {structured.specialists.reduce((a, s) => a + s.ms, structured.router.ms)}</div>
              <div>model: {structured.router.model}</div>
            </>
          ) : typeof trace === "string" ? (
            <pre className="whitespace-pre-wrap text-fg-muted">{trace}</pre>
          ) : (
            <div className="text-fg-muted">No trace available.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function PipelineNode({
  label, sub, ms, position,
}: {
  label: string; sub: string; ms: number; position: "first" | "middle" | "last";
}) {
  const radius =
    position === "first" ? "rounded-t-lg md:rounded-l-lg md:rounded-t-none"
    : position === "last" ? "rounded-b-lg md:rounded-r-lg md:rounded-b-none"
    : "";
  const border =
    position === "last"
      ? "border border-border"
      : "border border-border md:border-r-0";

  return (
    <div className={`relative flex-1 bg-bg-elev px-3.5 py-3 ${radius} ${border}`}>
      <div className="mb-1 flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-accent" />
        <span className="font-mono text-[11.5px] font-semibold">{label}</span>
      </div>
      <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[10.5px] text-fg-muted">{sub}</div>
      <div className="mt-1 font-mono text-[10.5px] text-fg-muted">{ms}ms</div>
      {position !== "last" && (
        <div className="absolute -right-[7px] top-1/2 z-10 hidden size-3.5 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-bg md:flex">
          <svg width="8" height="8" viewBox="0 0 14 14">
            <path d="M5 4l3 3-3 3" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" />
          </svg>
        </div>
      )}
    </div>
  );
}
