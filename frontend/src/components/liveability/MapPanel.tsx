"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useRef } from "react";
import { Layers3, MapPinned, Shield } from "lucide-react";
import { Suburb, Weights } from "./types";
import { scoreSuburb } from "./utils";

type RankedSuburb = Suburb & { computedScore: number };

type MapPanelProps = {
  suburbs: Suburb[];
  ranked: RankedSuburb[];
  selectedSuburbId: string | null;
  onSelectSuburb: (name: string) => void;
  layer: string;
  onLayerChange: (layer: string) => void;
  weights: Weights;
};

const layers = ["Liveability", "Safety", "Transport", "Lifestyle"];

const HEAT_STOPS = [
  { t: 0, color: { r: 59, g: 130, b: 246 } },
  { t: 0.34, color: { r: 99, g: 102, b: 241 } },
  { t: 0.68, color: { r: 249, g: 115, b: 22 } },
  { t: 1, color: { r: 239, g: 68, b: 68 } }
];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function smoothClosedPolygon(points: L.LatLngTuple[], segments = 10) {
  if (points.length < 3) return points;

  const n = points.length;
  const result: L.LatLngTuple[] = [];
  const getPoint = (index: number) => points[(index + n) % n];

  for (let i = 0; i < n; i += 1) {
    const p0 = getPoint(i - 1);
    const p1 = getPoint(i);
    const p2 = getPoint(i + 1);
    const p3 = getPoint(i + 2);

    for (let j = 0; j < segments; j += 1) {
      const t = j / segments;
      const t2 = t * t;
      const t3 = t2 * t;

      const lat =
        0.5 *
        ((2 * p1[0]) +
          (-p0[0] + p2[0]) * t +
          (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
          (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3);

      const lng =
        0.5 *
        ((2 * p1[1]) +
          (-p0[1] + p2[1]) * t +
          (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
          (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);

      result.push([lat, lng]);
    }
  }

  return result;
}

function scoreToHeatColor(score: number) {
  const t = clamp(score, 0, 100) / 100;
  const nextIndex = HEAT_STOPS.findIndex((stop) => stop.t >= t);

  if (nextIndex <= 0) {
    const { r, g, b } = HEAT_STOPS[0].color;
    return `rgb(${r}, ${g}, ${b})`;
  }

  if (nextIndex === -1) {
    const { r, g, b } = HEAT_STOPS[HEAT_STOPS.length - 1].color;
    return `rgb(${r}, ${g}, ${b})`;
  }

  const prev = HEAT_STOPS[nextIndex - 1];
  const next = HEAT_STOPS[nextIndex];
  const localT = (t - prev.t) / (next.t - prev.t);

  const r = Math.round(prev.color.r + (next.color.r - prev.color.r) * localT);
  const g = Math.round(prev.color.g + (next.color.g - prev.color.g) * localT);
  const b = Math.round(prev.color.b + (next.color.b - prev.color.b) * localT);
  return `rgb(${r}, ${g}, ${b})`;
}

function layerValue(suburb: Suburb, layer: string, weights: Weights) {
  if (layer === "Liveability") return scoreSuburb(suburb, weights);
  if (layer === "Safety") return suburb.scoreBase.safety;
  if (layer === "Transport") return suburb.scoreBase.transport;
  return suburb.scoreBase.lifestyle;
}

export function MapPanel({
  suburbs,
  ranked,
  selectedSuburbId,
  onSelectSuburb,
  layer,
  onLayerChange,
  weights
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const overlaysRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    const container = mapContainerRef.current;
    if (!container) return;

    // Guard against fast-refresh where Leaflet container metadata can remain attached.
    if ((container as { _leaflet_id?: number })._leaflet_id) {
      delete (container as { _leaflet_id?: number })._leaflet_id;
    }

    const map = L.map(container, {
      zoomControl: false,
      scrollWheelZoom: true,
      attributionControl: true
    }).setView([-33.8688, 151.2093], 13);

    L.control.zoom({ position: "topright" }).addTo(map);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; OpenStreetMap contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20,
      subdomains: "abcd"
    }).addTo(map);

    // Add labels as a separate subtle layer.
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; OpenStreetMap contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20,
      subdomains: "abcd",
      opacity: 0.75
    }).addTo(map);

    if (suburbs.length > 0) {
      const bounds = L.latLngBounds([] as L.LatLngTuple[]);
      suburbs.forEach((suburb) => {
        (suburb.polygon as L.LatLngTuple[]).forEach((point) => bounds.extend(point));
      });

      if (bounds.isValid()) {
        map.fitBounds(bounds.pad(0.08), {
          maxZoom: 15,
          animate: false
        });
      }
    }

    const overlayGroup = L.layerGroup().addTo(map);

    mapRef.current = map;
    overlaysRef.current = overlayGroup;

    return () => {
      overlayGroup.clearLayers();
      map.remove();
      mapRef.current = null;
      overlaysRef.current = null;
    };
  }, [suburbs]);

  useEffect(() => {
    const overlayGroup = overlaysRef.current;
    if (!overlayGroup) return;

    overlayGroup.clearLayers();

    suburbs.forEach((suburb) => {
      const value = layerValue(suburb, layer, weights);
      const heatColor = scoreToHeatColor(value);
      const opacity = selectedSuburbId && selectedSuburbId !== suburb.id ? 0.15 : 0.52;
      const isSelected = selectedSuburbId === suburb.id;
      const smoothPolygon = smoothClosedPolygon(suburb.polygon as L.LatLngTuple[], 9);

      const polygon = L.polygon(smoothPolygon as L.LatLngExpression[], {
        color: isSelected ? "#f8fafc" : heatColor,
        fillColor: heatColor,
        fillOpacity: opacity,
        weight: isSelected ? 2.2 : 0.8,
        smoothFactor: 0,
        lineJoin: "round",
        lineCap: "round"
      });

      polygon.on("click", () => onSelectSuburb(suburb.name));
      polygon.addTo(overlayGroup);

      const circle = L.circle(suburb.center as L.LatLngExpression, {
        radius: 260 + value * 6,
        color: heatColor,
        fillColor: heatColor,
        fillOpacity: opacity * 0.14,
        weight: 0
      });

      circle.addTo(overlayGroup);

      const glow = L.circle(suburb.center as L.LatLngExpression, {
        radius: 380 + value * 7,
        color: heatColor,
        fillColor: heatColor,
        fillOpacity: opacity * 0.08,
        weight: 0
      });

      glow.addTo(overlayGroup);

      const label = L.marker(suburb.center as L.LatLngExpression, {
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: "suburb-name-label",
          html: `<span style="
            color: ${isSelected ? "#0f172a" : "#1e293b"};
            font-size: ${isSelected ? "36px" : "32px"};
            font-weight: 800;
            letter-spacing: 0.01em;
            text-shadow: 0 2px 6px rgba(255,255,255,0.65), 0 0 1px rgba(255,255,255,0.8);
            white-space: nowrap;
            transform: translate(-50%, -50%);
            display: inline-block;
          ">${suburb.name}</span>`
        })
      });

      label.addTo(overlayGroup);

      if (isSelected) {
        polygon.bringToFront();
      }
    });
  }, [suburbs, layer, weights, selectedSuburbId, onSelectSuburb]);

  return (
    <section className="relative h-full overflow-hidden bg-[radial-gradient(circle_at_30%_18%,rgba(254,215,170,0.3),transparent_28%),linear-gradient(180deg,#eff2f8,#e9edf6)]">
      <div className="absolute right-3 top-3 z-[450] flex max-w-[52%] flex-wrap justify-end gap-1.5">
        {layers.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => onLayerChange(name)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold shadow-[0_8px_20px_rgba(15,23,42,0.08)] backdrop-blur transition ${
              layer === name
                ? "border-fuchsia-300 bg-gradient-to-r from-blue-500/90 to-pink-500/90 text-white"
                : "border-white/80 bg-white/88 text-slate-600 hover:border-slate-400 hover:text-slate-800"
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      <div ref={mapContainerRef} className="liveability-map h-full w-full" />

      <div className="pointer-events-none absolute bottom-6 right-3 z-[450] rounded-xl border border-white/70 bg-white/86 p-2 shadow-[0_10px_28px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="mb-1 flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.06em] text-slateMuted">
          <Layers3 size={10} />
          {layer} heat scale
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium text-slate-500">Cold</span>
          <div className="h-2 w-24 rounded-full bg-gradient-to-r from-blue-500 via-indigo-500 via-orange-500 to-red-500" />
          <span className="text-[10px] font-medium text-slate-500">Hot</span>
        </div>
      </div>

      <div className="scrollbar-none absolute inset-x-0 bottom-0 z-[450] flex gap-2 overflow-x-auto bg-gradient-to-t from-slate-900/20 via-slate-900/5 to-transparent pb-3 pl-2 pr-3 pt-6 md:pl-[370px]">
        {ranked.map((suburb, index) => (
          
          <button
            key={suburb.id}
            type="button"
            onClick={() => onSelectSuburb(suburb.name)}
            className={`min-w-[146px] flex-shrink-0 rounded-2xl border p-3 text-left shadow-[0_10px_24px_rgba(15,23,42,0.08)] backdrop-blur transition hover:-translate-y-0.5 hover:shadow-cardLg ${
              selectedSuburbId === suburb.id
                ? "border-slate-500 bg-white"
                : "border-white/80 bg-white/86"
            }`}
          >
            <div className="mb-1 flex items-start justify-between">
              <div>
                <p className="text-[9px] font-semibold text-slateMuted">#{index + 1}</p>
                <p className="text-xs font-bold text-slate-800">{suburb.name}</p>
              </div>
              <p className="text-2xl font-extrabold" style={{ color: scoreToHeatColor(layerValue(suburb, layer, weights)) }}>
                {suburb.computedScore}
              </p>
            </div>
            <div className="h-1 rounded bg-slate-200/70">
              <div
                className="h-1 rounded"
                style={{
                  width: `${suburb.computedScore}%`,
                  backgroundColor: scoreToHeatColor(layerValue(suburb, layer, weights))
                }}
              />
            </div>
          </button>
        ))}
      </div>

      <div className="pointer-events-none absolute right-3 top-14 z-[450] rounded-xl border border-white/80 bg-white/86 px-3 py-2 text-xs shadow-[0_10px_24px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="mb-1 flex items-center gap-1 text-slateMuted">
          <MapPinned size={12} />
          Sydney inner city demo
        </div>
        <div className="flex items-center gap-1 font-semibold text-slateText">
          <Shield size={12} className="text-emerald-600" />
          Civic + social overlays
        </div>
      </div>
    </section>
  );
}
