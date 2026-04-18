"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { HexagonGrid, HexRow } from "../../components/liveability/HexagonGrid";
import { SharedBrand } from "../../components/liveability/SharedBrand";

const API_BASE =
  (typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_API_URL &&
    process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")) ||
  "http://localhost:8000";

type SortKey = "score" | "posts" | "alpha";
type FilterKey = "all" | "cached" | "top25";

type FetchState =
  | { status: "loading" }
  | { status: "ok"; rows: HexRow[] }
  | { status: "error"; message: string };

export default function OverviewPage() {
  const router = useRouter();
  const [state, setState] = useState<FetchState>({ status: "loading" });
  const [sort, setSort] = useState<SortKey>("score");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetch(`${API_BASE}/api/reddit/summary`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Summary request failed (${res.status})`);
        }
        return (await res.json()) as { suburbs: HexRow[] };
      })
      .then((data) => {
        if (!cancelled) setState({ status: "ok", rows: data.suburbs ?? [] });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Unknown error";
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ordered = useMemo(() => {
    if (state.status !== "ok") return [] as HexRow[];
    const q = query.trim().toLowerCase();
    let rows = state.rows.slice();

    if (filter === "cached") {
      rows = rows.filter((r) => r.cached);
    } else if (filter === "top25") {
      rows = rows.filter((r) => r.cached && r.score !== null);
      rows.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
      rows = rows.slice(0, 25);
    }

    if (q) {
      rows = rows.filter((r) => r.suburb.toLowerCase().includes(q));
    }

    if (sort === "score") {
      rows.sort((a, b) => {
        const sa = a.score ?? -1;
        const sb = b.score ?? -1;
        return sb - sa;
      });
    } else if (sort === "posts") {
      rows.sort((a, b) => b.post_count - a.post_count);
    } else {
      rows.sort((a, b) => a.suburb.localeCompare(b.suburb));
    }
    return rows;
  }, [state, sort, filter, query]);

  const stats = useMemo(() => {
    if (state.status !== "ok") return null;
    const cached = state.rows.filter((r) => r.cached).length;
    const total = state.rows.length;
    const totalPosts = state.rows.reduce((acc, r) => acc + r.post_count, 0);
    const scores = state.rows
      .map((r) => r.score)
      .filter((s): s is number => s !== null);
    const avg =
      scores.length > 0
        ? scores.reduce((a, b) => a + b, 0) / scores.length
        : null;
    return { cached, total, totalPosts, avg };
  }, [state]);

  function handleSelect(suburb: string) {
    router.push(`/suburb/${encodeURIComponent(suburb)}`);
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_72%_8%,rgba(251,146,60,0.10),transparent_32%),linear-gradient(180deg,#f7f8fb,#eef1f7)] font-['Manrope',sans-serif] text-slateText">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/80 bg-white/70 px-5 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <SharedBrand compact />
          <div className="h-5 w-px bg-slate-200" />
          <Link
            href="/"
            className="text-[12px] font-semibold text-slate-600 transition hover:text-slate-900"
          >
            ← Back to map
          </Link>
        </div>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
          Hex Overview · Liveability grid
        </span>
      </header>

      <section className="mx-auto w-full max-w-6xl px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
              Greater Sydney
            </p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              Liveability hex grid
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              One hexagon per suburb. Fill colour = composite liveability score
              from our aspect-based NLP pipeline over r/sydney. Click any hex to
              drill into a suburb&apos;s full analysis.
            </p>
          </div>
          {stats ? (
            <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium text-slate-600">
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
                {stats.total} suburbs
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
                {stats.cached} analysed
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
                {stats.totalPosts.toLocaleString()} posts
              </span>
              {stats.avg !== null ? (
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1">
                  avg {Math.round(stats.avg * 100)}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <input
            type="search"
            placeholder="Filter suburbs…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full max-w-xs rounded-full border border-slate-200 bg-white px-4 py-2 text-[13px] shadow-card outline-none placeholder:text-slate-400 focus:border-slate-400"
          />
          <SegmentedControl<SortKey>
            label="Sort"
            value={sort}
            onChange={setSort}
            options={[
              { key: "score", label: "Score" },
              { key: "posts", label: "Posts" },
              { key: "alpha", label: "A–Z" },
            ]}
          />
          <SegmentedControl<FilterKey>
            label="View"
            value={filter}
            onChange={setFilter}
            options={[
              { key: "all", label: "All" },
              { key: "cached", label: "Analysed" },
              { key: "top25", label: "Top 25" },
            ]}
          />
        </div>

        <div className="mt-6 rounded-xl2 border border-slate-200 bg-white p-4 shadow-card sm:p-6">
          {state.status === "loading" ? (
            <LoadingGrid />
          ) : state.status === "error" ? (
            <ErrorCard message={state.message} />
          ) : ordered.length === 0 ? (
            <EmptyState />
          ) : (
            <HexagonGrid rows={ordered} onSelect={handleSelect} />
          )}
          <ScaleLegend />
        </div>

        {state.status === "ok" && ordered.length > 0 ? (
          <p className="mt-3 text-center text-[11px] text-slate-500">
            Hover any hex for details · click to open the full NLP analysis.
          </p>
        ) : null}
      </section>

      <footer className="mx-auto max-w-6xl px-5 pb-10 pt-2 text-center text-[11px] text-slate-400">
        Pipeline: BART-MNLI aspects · DistilRoBERTa emotion · VADER sentiment ·
        r/sydney via Arctic Shift
      </footer>
    </main>
  );
}

function SegmentedControl<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { key: T; label: string }[];
}) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white p-1 shadow-card">
      <span className="px-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
        {label}
      </span>
      {options.map((opt) => {
        const active = opt.key === value;
        return (
          <button
            key={opt.key}
            type="button"
            onClick={() => onChange(opt.key)}
            className={`rounded-full px-3 py-1 text-[11px] font-semibold transition ${
              active
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function ScaleLegend() {
  const stops = [
    { label: "0", colour: "#ef4444" },
    { label: "30", colour: "#f87171" },
    { label: "45", colour: "#fbbf24" },
    { label: "50", colour: "#fde68a" },
    { label: "55", colour: "#a7f3d0" },
    { label: "65", colour: "#34d399" },
    { label: "100", colour: "#10b981" },
  ];
  return (
    <div className="mt-4 flex items-center justify-center gap-2 text-[10px] text-slate-500">
      <span className="uppercase tracking-[0.12em]">Liveability score</span>
      <div className="flex items-center gap-0.5">
        {stops.map((s) => (
          <div
            key={s.label}
            className="flex flex-col items-center"
            style={{ minWidth: 22 }}
          >
            <div
              className="h-3 w-full rounded-sm"
              style={{ background: s.colour }}
            />
            <span className="mt-0.5">{s.label}</span>
          </div>
        ))}
        <div className="ml-3 flex flex-col items-center" style={{ minWidth: 22 }}>
          <div
            className="h-3 w-full rounded-sm border border-slate-300"
            style={{ background: "#e2e8f0" }}
          />
          <span className="mt-0.5">n/a</span>
        </div>
      </div>
    </div>
  );
}

function LoadingGrid() {
  return (
    <div className="flex min-h-[360px] items-center justify-center">
      <div className="flex items-center gap-2 text-[12px] text-slate-500">
        <span className="inline-block h-2 w-2 animate-ping rounded-full bg-slate-400" />
        Loading suburb summaries…
      </div>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-6">
      <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-rose-700">
        Could not load overview
      </h3>
      <p className="mt-2 text-[13px] text-rose-800">{message}</p>
      <p className="mt-2 text-[12px] text-rose-600">
        Make sure the backend is running on{" "}
        <code className="rounded bg-white/70 px-1">{API_BASE}</code> and that
        the Arctic Shift data has been processed (see README).
      </p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center text-center text-[13px] text-slate-500">
      <p className="font-semibold text-slate-700">No suburbs match that filter.</p>
      <p className="mt-1">Try switching the view or clearing the search.</p>
    </div>
  );
}
