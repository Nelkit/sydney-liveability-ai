"use client";

import dynamic from "next/dynamic";
import { ScoreGauge } from "@/components/ui/ScoreGauge";
import type { SuburbScore } from "@/types/api";

const MapPanel = dynamic(
  () => import("@/components/liveability/MapPanel").then((m) => m.MapPanel),
  { ssr: false }
);
const EMPTY_WEIGHTS = { transport: 0, safety: 0, lifestyle: 0, afford: 0, proximity: 0 };

type Props = {
  name: string;
  data: SuburbScore;
  accent: string;
  side: "left" | "right";
};

function Stat({ label, v }: { label: string; v: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-border bg-bg-elev px-[7px] py-px font-mono text-[10.5px]">
      <span className="text-fg-muted">{label}</span>
      <span className="font-semibold">{v}</span>
    </span>
  );
}

function Fact({ label, v }: { label: string; v: number }) {
  return (
    <div className="rounded-lg border border-border bg-bg p-2.5">
      <div className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-fg-muted">{label}</div>
      <div className="mt-0.5 font-mono text-lg font-semibold">{v}</div>
    </div>
  );
}

export function SuburbHero({ name, data, accent, side }: Props) {
  return (
    <div className={`p-4 sm:p-6 ${side === "left" ? "lg:border-r lg:border-border" : ""}`}>
      <div className="mb-4 flex items-start gap-3 sm:gap-4">
        <div className="relative shrink-0">
          <ScoreGauge value={data.score} size={76} label="liveability" />
          <div
            className="pointer-events-none absolute inset-[-3px] rounded-full border-2 opacity-25"
            style={{ borderColor: accent }}
          />
        </div>
        <div className="flex-1 min-w-0">
          {data.sa4 && data.sa4 !== "N/A" && <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted truncate">{data.sa4}</div>}
          <div className="text-xl sm:text-2xl font-semibold tracking-[-0.02em] truncate" style={{ color: accent }}>
            {name}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            <Stat label="walk" v={data.walkability.toFixed(1)} />
            <Stat label="fac"  v={data.facilities.toFixed(1)} />
            <Stat label="sent" v={typeof data.sentiment === "number" ? `${Math.round(data.sentiment)}%` : "n/a"} />
          </div>
        </div>
      </div>

      {/* Mini map in locator mode */}
      <div className="overflow-hidden rounded-lg" style={{ height: 130 }}>
        <MapPanel
          suburbs={[]}
          ranked={[]}
          isLoading={false}
          selectedSuburbId={null}
          onSelectSuburb={() => {}}
          layer="Liveability"
          onLayerChange={() => {}}
          weights={EMPTY_WEIGHTS}
          activeSuburbs={[name]}
          hideRanking
        />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4 sm:gap-2">
        <Fact label="cafes"       v={data.cafes} />
        <Fact label="restaurants" v={data.restaurants} />
        <Fact label="parks"       v={data.parks} />
        <Fact label="playgrounds" v={data.playgrounds} />
      </div>
    </div>
  );
}
