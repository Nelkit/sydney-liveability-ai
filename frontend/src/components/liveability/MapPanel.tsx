"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Layers3 } from "lucide-react";
import { Suburb, Weights } from "./types";
import { scoreSuburb } from "./utils";
import { useCitationHover } from "@/context/CitationHoverContext";

type RankedSuburb = Suburb & { computedScore: number };

type MapPanelProps = {
  suburbs: Suburb[];
  ranked: RankedSuburb[];
  isLoading: boolean;
  loadingLabel?: string;
  isVisible?: boolean;
  selectedSuburbId: string | null;
  onSelectSuburb: (name: string) => void;
  layer: string;
  onLayerChange: (layer: string) => void;
  weights: Weights;
  // New props from redesign
  activeSuburbs?: string[];
  hoveredSuburb?: string | null;
  onSuburbHover?: (name: string | null) => void;
  hideRanking?: boolean;
};

const layers = ["Liveability", "Safety", "Transport", "Lifestyle"];
const SMALL_LABEL_MIN_ZOOM = 15;

type ColorStop = { t: number; color: { r: number; g: number; b: number } };

const LAYER_HEAT_STOPS: Record<string, ColorStop[]> = {
  Liveability: [
    { t: 0,    color: { r: 148, g: 163, b: 184 } }, // slate-400  — low
    { t: 0.34, color: { r: 99,  g: 102, b: 241 } }, // indigo-500
    { t: 0.68, color: { r: 139, g: 92,  b: 246 } }, // violet-500
    { t: 1,    color: { r: 79,  g: 70,  b: 229 } }, // indigo-600 — high
  ],
  Safety: [
    { t: 0,    color: { r: 248, g: 113, b: 113 } }, // red-400    — low (dangerous)
    { t: 0.4,  color: { r: 251, g: 191, b: 36  } }, // amber-400
    { t: 0.75, color: { r: 74,  g: 222, b: 128 } }, // green-400
    { t: 1,    color: { r: 22,  g: 163, b: 74  } }, // green-600  — high (safe)
  ],
  Transport: [
    { t: 0,    color: { r: 148, g: 163, b: 184 } }, // slate-400  — low
    { t: 0.4,  color: { r: 56,  g: 189, b: 248 } }, // sky-400
    { t: 0.75, color: { r: 14,  g: 165, b: 233 } }, // sky-500
    { t: 1,    color: { r: 2,   g: 132, b: 199 } }, // sky-600    — high
  ],
  Lifestyle: [
    { t: 0,    color: { r: 148, g: 163, b: 184 } }, // slate-400  — low
    { t: 0.4,  color: { r: 251, g: 191, b: 36  } }, // amber-400
    { t: 0.75, color: { r: 249, g: 115, b: 22  } }, // orange-500
    { t: 1,    color: { r: 234, g: 88,  b: 12  } }, // orange-600 — high
  ],
};

function stopsToGradientCSS(stops: ColorStop[]): string {
  const parts = stops.map(({ t, color: { r, g, b } }) => `rgb(${r},${g},${b}) ${t * 100}%`);
  return `linear-gradient(to right, ${parts.join(", ")})`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function smoothClosedPolygon(points: L.LatLngTuple[], segments = 10) {
  if (points.length < 3) return points;
  const n = points.length;
  const result: L.LatLngTuple[] = [];
  const getPoint = (index: number) => points[(index + n) % n];

  for (let i = 0; i < n; i++) {
    const p0 = getPoint(i - 1);
    const p1 = getPoint(i);
    const p2 = getPoint(i + 1);
    const p3 = getPoint(i + 2);
    for (let j = 0; j < segments; j++) {
      const t = j / segments;
      const t2 = t * t;
      const t3 = t2 * t;
      const lat = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3);
      const lng = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);
      result.push([lat, lng]);
    }
  }
  return result;
}

function scoreToHeatColor(score: number, layer = "Liveability") {
  const stops = LAYER_HEAT_STOPS[layer] ?? LAYER_HEAT_STOPS.Liveability;
  const t = clamp(score, 0, 100) / 100;
  const nextIndex = stops.findIndex((stop) => stop.t >= t);
  if (nextIndex <= 0) { const { r, g, b } = stops[0].color; return `rgb(${r}, ${g}, ${b})`; }
  if (nextIndex === -1) { const { r, g, b } = stops[stops.length - 1].color; return `rgb(${r}, ${g}, ${b})`; }
  const prev = stops[nextIndex - 1];
  const next = stops[nextIndex];
  const localT = (t - prev.t) / (next.t - prev.t);
  const r = Math.round(prev.color.r + (next.color.r - prev.color.r) * localT);
  const g = Math.round(prev.color.g + (next.color.g - prev.color.g) * localT);
  const b = Math.round(prev.color.b + (next.color.b - prev.color.b) * localT);
  return `rgb(${r}, ${g}, ${b})`;
}

function layerValue(suburb: Suburb, layer: string, weights: Weights) {
  if (layer === "Liveability") return scoreSuburb(suburb, weights);
  if (layer === "Safety")      return suburb.scoreBase.safety;
  if (layer === "Transport")   return suburb.scoreBase.transport;
  return suburb.scoreBase.lifestyle;
}

function normalizeSuburbName(name: string) {
  return name.replace(" (NSW)", "").trim().toLowerCase();
}

function getFeatureSuburbName(feature: GeoJSON.Feature) {
  const props = feature.properties as Record<string, unknown> | null;
  const rawName = props?.SAL_NAME21;
  if (typeof rawName !== "string") return null;
  return normalizeSuburbName(rawName);
}

function getFeatureSuburbLabel(feature: GeoJSON.Feature) {
  const props = feature.properties as Record<string, unknown> | null;
  const rawName = props?.SAL_NAME21;
  if (typeof rawName !== "string") return null;
  return rawName.replace(" (NSW)", "").trim();
}

export function MapPanel({
  suburbs,
  ranked,
  isLoading,
  loadingLabel = "Loading civic data",
  selectedSuburbId,
  onSelectSuburb,
  layer,
  onLayerChange,
  weights,
  activeSuburbs = [],
  hoveredSuburb,
  onSuburbHover,
  isVisible = true,
  hideRanking = false,
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef          = useRef<L.Map | null>(null);
  const overlaysRef     = useRef<L.LayerGroup | null>(null);
  const [suburbsGeoJson, setSuburbsGeoJson] = useState<GeoJSON.FeatureCollection | null>(null);
  const [geoJsonLoaded, setGeoJsonLoaded]   = useState(false);
  const [mapZoom, setMapZoom]               = useState<number | null>(null);
  const hasFittedBoundsRef    = useRef(false);
  const previousLoadingRef    = useRef(isLoading);
  const previousRankedLenRef  = useRef(ranked.length);

  // Subscribe to citation hover — highlight cited suburbs on the map
  const { hoveredCite } = useCitationHover();
  const citationActiveSuburbs = useMemo(() => hoveredCite?.suburbs ?? [], [hoveredCite]);

  // Effective active suburbs: citation hover > prop hover > activeSuburbs prop > selectedSuburbId
  const effectiveActive = useMemo(() => {
    if (citationActiveSuburbs.length > 0) return citationActiveSuburbs;
    if (hoveredSuburb) return [hoveredSuburb];
    return activeSuburbs;
  }, [citationActiveSuburbs, hoveredSuburb, activeSuburbs]);

  const suburbsByName = useMemo(() => {
    const byName = new Map<string, Suburb>();
    suburbs.forEach((s) => byName.set(normalizeSuburbName(s.name), s));
    return byName;
  }, [suburbs]);

  const activeSet = useMemo(() => {
    return new Set(effectiveActive.map((s) => s.toLowerCase()));
  }, [effectiveActive]);

  useEffect(() => {
    let cancelled = false;
    async function loadGeoJson() {
      try {
        const urls = ["/suburbs.geojson", "/layers/suburbs.geojson"];
        let data: GeoJSON.FeatureCollection | null = null;
        for (const url of urls) {
          const response = await fetch(url);
          if (!response.ok) continue;
          data = (await response.json()) as GeoJSON.FeatureCollection;
          break;
        }
        if (!data) throw new Error("Unable to load suburbs layer");
        if (!cancelled) { setSuburbsGeoJson(data); setGeoJsonLoaded(true); }
      } catch {
        if (!cancelled) { setSuburbsGeoJson(null); setGeoJsonLoaded(true); }
      }
    }
    loadGeoJson();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const container = mapContainerRef.current;
    if (!container) return;
    if ((container as { _leaflet_id?: number })._leaflet_id) {
      delete (container as { _leaflet_id?: number })._leaflet_id;
    }
    const map = L.map(container, { zoomControl: false, scrollWheelZoom: true, attributionControl: true })
      .setView([-33.8688, 151.2093], 13);

    // zoom control handled by custom React buttons
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; OpenStreetMap contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20, subdomains: "abcd",
    }).addTo(map);
    // Labels only shown at high zoom; suppressed at lower zoom to avoid collision
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; OpenStreetMap contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20, subdomains: "abcd", opacity: 0.5, minZoom: 14,
    }).addTo(map);

    const overlayGroup = L.layerGroup().addTo(map);
    setMapZoom(map.getZoom());
    map.on("zoomend", () => setMapZoom(map.getZoom()));
    mapRef.current = map;
    overlaysRef.current = overlayGroup;
    hasFittedBoundsRef.current = false;

    // When the container goes from hidden (0×0) to visible, Leaflet's internal
    // _size is stale. Calling invalidateSize() recomputes it so flyToBounds
    // and coordinate projection don't produce NaN from division-by-zero.
    const ro = new ResizeObserver(() => {
      const m = mapRef.current;
      if (m) m.invalidateSize();
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      overlayGroup.clearLayers();
      map.remove();
      mapRef.current = null;
      overlaysRef.current = null;
    };
  }, []);

  // When the map tab becomes visible on mobile, Leaflet's size is stale.
  // invalidateSize() recomputes it, then re-center on Sydney if zoom is wrong.
  useEffect(() => {
    if (!isVisible) return;
    const map = mapRef.current;
    if (!map) return;
    setTimeout(() => {
      map.invalidateSize();
      if (map.getZoom() < 10) {
        map.setView([-33.8688, 151.2093], 13);
      }
    }, 50);
  }, [isVisible]);

  useEffect(() => {
    if (previousLoadingRef.current && !isLoading) hasFittedBoundsRef.current = false;
    previousLoadingRef.current = isLoading;
  }, [isLoading]);

  // Reset zoom guard when ranked data arrives for the first time (e.g. navigating from onboarding
  // while civic fetch already completed — isLoading never transitions true→false on this mount)
  useEffect(() => {
    const prev = previousRankedLenRef.current;
    previousRankedLenRef.current = ranked.length;
    if (prev === 0 && ranked.length > 0) hasFittedBoundsRef.current = false;
  }, [ranked.length]);

  // Fly to active suburb(s) when chat response arrives
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !suburbsGeoJson || activeSuburbs.length === 0) return;

    const targetNames = new Set(activeSuburbs.map((s) => s.toLowerCase()));
    const matchingFeatures = suburbsGeoJson.features.filter((f) => {
      const name = getFeatureSuburbName(f as GeoJSON.Feature);
      return name && targetNames.has(name);
    });

    if (matchingFeatures.length === 0) return;

    const tempLayer = L.geoJSON({ type: "FeatureCollection", features: matchingFeatures } as GeoJSON.FeatureCollection);
    try {
      const bounds = tempLayer.getBounds();
      if (bounds.isValid()) {
        map.flyToBounds(bounds.pad(0.25), { maxZoom: 15, duration: 1.1 });
      }
    } catch {
      // skip
    }
  }, [activeSuburbs, suburbsGeoJson]);

  useEffect(() => {
    const overlayGroup = overlaysRef.current;
    const map = mapRef.current;
    if (!overlayGroup || !map || !geoJsonLoaded) return;
    overlayGroup.clearLayers();

    const hasActiveFilter = activeSet.size > 0;

    if (suburbsGeoJson) {
      // Base: all suburbs — dim when active filter is set
      const allSuburbsLayer = L.geoJSON(suburbsGeoJson, {
        style: (feature) => {
          if (!feature) return {};
          const name = getFeatureSuburbName(feature);
          const isActive = name ? activeSet.has(name) : false;
          if (hasActiveFilter && isActive) return { opacity: 0, fillOpacity: 0 }; // drawn by activeLayer below
          return {
            color: "#64748b",
            fillColor: "#64748b",
            fillOpacity: hasActiveFilter ? 0.04 : 0.10,
            weight: 0.6,
            opacity: hasActiveFilter ? 0.25 : 0.5,
          };
        },
        interactive: false,
      });
      allSuburbsLayer.addTo(overlayGroup);

      // Active suburbs highlight layer — works for any suburb in GeoJSON, not just civicData
      if (hasActiveFilter) {
        const activeLayer = L.geoJSON(suburbsGeoJson, {
          filter: (feature) => {
            if (!feature) return false;
            const name = getFeatureSuburbName(feature);
            return Boolean(name && activeSet.has(name));
          },
          style: {
            color: "#ffffff",
            fillColor: "rgb(109, 40, 217)",
            fillOpacity: 0.72,
            weight: 3,
            opacity: 1,
          },
          onEachFeature: (feature, layerItem) => {
            const name = getFeatureSuburbName(feature);
            if (!name) return;
            const label = L.marker(
              (layerItem as unknown as { getBounds: () => L.LatLngBounds }).getBounds?.().getCenter?.() ?? L.latLng(0, 0),
              {
                interactive: false,
                keyboard: false,
                icon: L.divIcon({
                  className: "suburb-name-label",
                  html: `<span style="color:#0f172a;font-size:13px;font-weight:700;letter-spacing:0.01em;text-shadow:0 1px 3px rgba(255,255,255,0.9);white-space:nowrap;transform:translate(-50%,-50%);display:inline-block;">${name.replace(/\b\w/g, (c) => c.toUpperCase())}</span>`,
                }),
              }
            );
            label.addTo(overlayGroup);
          },
        });
        activeLayer.addTo(overlayGroup);
      }

      // Highlighted layer for backend suburbs
      const highlightedLayer = L.geoJSON(suburbsGeoJson, {
        filter: (feature) => {
          if (!feature) return false;
          const featureName = getFeatureSuburbName(feature);
          return Boolean(featureName && suburbsByName.has(featureName));
        },
        style: (feature) => {
          if (!feature) return {};
          const featureName = getFeatureSuburbName(feature);
          if (!featureName) return {};
          const suburb = suburbsByName.get(featureName);
          if (!suburb) return {};

          const value = layerValue(suburb, layer, weights);
          const heatColor = scoreToHeatColor(value, layer);
          const isCited  = citationActiveSuburbs.map((s) => s.toLowerCase()).includes(featureName);
          const isActive = activeSet.has(featureName);
          const isSelected = selectedSuburbId === suburb.id;

          let fillOpacity = 0.52;
          if (hasActiveFilter && !isActive && !isCited) fillOpacity = 0.08;
          if (isActive) fillOpacity = 0.82;
          if (isCited) fillOpacity = 0.75;

          return {
            color: isActive ? "#ffffff" : isCited ? "#f8fafc" : isSelected ? "#f8fafc" : heatColor,
            fillColor: isActive ? "oklch(0.55 0.18 285)" : heatColor,
            fillOpacity,
            weight: isActive ? 3 : isSelected || isCited ? 2.5 : 0.8,
          };
        },
        onEachFeature: (feature, layerItem) => {
          const featureName = getFeatureSuburbName(feature);
          if (!featureName) return;
          const suburb = suburbsByName.get(featureName);
          if (!suburb) return;

          layerItem.on("click", () => onSelectSuburb(suburb.name));
          layerItem.on("mouseover", () => onSuburbHover?.(suburb.name));
          layerItem.on("mouseout",  () => onSuburbHover?.(null));

          if (selectedSuburbId === suburb.id) {
            if ("bringToFront" in layerItem) (layerItem as { bringToFront: () => void }).bringToFront();
          }
        },
      });
      highlightedLayer.addTo(overlayGroup);

      if (!hasFittedBoundsRef.current && !isLoading) {
        try {
          const bounds = highlightedLayer.getBounds();
          map.flyToBounds(bounds.pad(0.08), { maxZoom: 15, duration: 0.9 });
          hasFittedBoundsRef.current = true;
        } catch {
          // Polygon has NaN coordinates — skip flyToBounds silently
        }
      }

      // Labels ONLY for active/selected suburbs — suppress for all others to fix collision
      const activeSuburbsForLabels = effectiveActive.length > 0 ? effectiveActive : (selectedSuburbId ? suburbs.filter((s) => s.id === selectedSuburbId).map((s) => s.name) : []);
      if (activeSuburbsForLabels.length > 0 || (mapZoom ?? map.getZoom()) >= SMALL_LABEL_MIN_ZOOM) {
        highlightedLayer.eachLayer((layerItem) => {
          const lf = layerItem as L.Layer & { feature?: GeoJSON.Feature };
          const feature = lf.feature;
          if (!feature) return;
          const normalizedName = getFeatureSuburbName(feature);
          if (!normalizedName) return;

          const suburb = suburbsByName.get(normalizedName);
          if (!suburb) return;

          const isActive = activeSet.has(normalizedName) || citationActiveSuburbs.map((s) => s.toLowerCase()).includes(normalizedName);
          // Only show labels for active suburbs at normal zoom; show all at high zoom
          if (!isActive && (mapZoom ?? map.getZoom()) < SMALL_LABEL_MIN_ZOOM) return;

          if (!("getBounds" in layerItem)) return;
          const bounds = (layerItem as { getBounds: () => L.LatLngBounds }).getBounds();
          if (!bounds.isValid()) return;

          const label = L.marker(bounds.getCenter(), {
            interactive: false,
            keyboard: false,
            icon: L.divIcon({
              className: "suburb-name-label",
              html: `<span style="
                color: ${isActive ? "#0f172a" : "#334155"};
                font-size: ${isActive ? "13px" : "11px"};
                font-weight: ${isActive ? "700" : "600"};
                letter-spacing: 0.01em;
                text-shadow: 0 1px 3px rgba(255,255,255,0.9);
                white-space: nowrap;
                transform: translate(-50%, -50%);
                display: inline-block;
              ">${suburb.name}</span>`,
            }),
          });
          label.addTo(overlayGroup);
        });
      }
    } else {
      // Fallback: legacy polygon rendering
      suburbs.forEach((suburb) => {
        const value = layerValue(suburb, layer, weights);
        const heatColor = scoreToHeatColor(value, layer);
        const isActive   = activeSet.has(suburb.name.toLowerCase());
        const isSelected = selectedSuburbId === suburb.id;
        const opacity    = hasActiveFilter && !isActive ? 0.15 : (isSelected ? 0.60 : 0.52);
        const smoothPolygon = smoothClosedPolygon(suburb.polygon as L.LatLngTuple[], 9);
        const polygon = L.polygon(smoothPolygon as L.LatLngExpression[], {
          color: isSelected ? "#f8fafc" : heatColor,
          fillColor: heatColor, fillOpacity: opacity,
          weight: isSelected ? 2.2 : 0.8, smoothFactor: 0,
        });
        polygon.on("click", () => onSelectSuburb(suburb.name));
        polygon.on("mouseover", () => onSuburbHover?.(suburb.name));
        polygon.on("mouseout",  () => onSuburbHover?.(null));
        polygon.addTo(overlayGroup);
      });
    }

    suburbs.forEach((suburb) => {
      const value = layerValue(suburb, layer, weights);
      const heatColor = scoreToHeatColor(value, layer);
      const isActive  = activeSet.has(suburb.name.toLowerCase());
      const opacity   = hasActiveFilter && !isActive ? 0.05 : 0.52;

      [
        { radius: 260 + value * 6, opacityMult: 0.14 },
        { radius: 380 + value * 7, opacityMult: 0.08 },
      ].forEach(({ radius, opacityMult }) => {
        L.circle(suburb.center as L.LatLngExpression, {
          radius, color: heatColor, fillColor: heatColor,
          fillOpacity: opacity * opacityMult, weight: 0,
          interactive: false, bubblingMouseEvents: false,
        }).addTo(overlayGroup);
      });
    });
  }, [suburbs, suburbsByName, suburbsGeoJson, geoJsonLoaded, mapZoom, layer, weights, selectedSuburbId, onSelectSuburb, isLoading, effectiveActive, activeSet, citationActiveSuburbs, onSuburbHover]);

  const legendGradient = stopsToGradientCSS(LAYER_HEAT_STOPS[layer] ?? LAYER_HEAT_STOPS.Liveability);

  return (
    <section className="relative h-full overflow-hidden bg-[radial-gradient(circle_at_30%_18%,rgba(254,215,170,0.3),transparent_28%),linear-gradient(180deg,#eff2f8,#e9edf6)]">
      {/* Layer switcher + zoom — left overlay */}
      <div className="absolute left-3 top-3 z-[450] flex flex-col items-start gap-2 max-w-[calc(100vw-5rem)]">
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none rounded-lg border border-border bg-bg p-[3px] shadow-float">
          {layers.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => onLayerChange(name)}
              className={`shrink-0 rounded-md border-none px-[10px] py-[5px] text-[11.5px] font-medium capitalize transition cursor-pointer ${
                layer === name
                  ? "bg-fg text-bg"
                  : "bg-transparent text-fg hover:bg-bg-elev"
              }`}
            >
              {name}
            </button>
          ))}
        </div>

        {/* Zoom buttons */}
        <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-bg shadow-float">
          <button
            type="button"
            onClick={() => mapRef.current?.zoomIn()}
            className="flex size-8 cursor-pointer items-center justify-center border-b border-border text-fg transition hover:bg-bg-elev"
            aria-label="Zoom in"
          >
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
              <path d="M7 3v8M3 7h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => mapRef.current?.zoomOut()}
            className="flex size-8 cursor-pointer items-center justify-center text-fg transition hover:bg-bg-elev"
            aria-label="Zoom out"
          >
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
              <path d="M3 7h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Legend + active suburbs badge — right */}
      <div className="absolute right-3 top-3 z-[450] flex flex-col items-end gap-2">
        <div className="rounded-[10px] border border-border bg-bg p-2 shadow-float">
          <div className="mb-1 flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.06em] text-fg-muted">
            <Layers3 size={10} />
            {layer}
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-fg-muted">Low</span>
            <div className="h-2 w-20 rounded-full" style={{ background: legendGradient }} />
            <span className="font-mono text-[10px] text-fg-muted">High</span>
          </div>
        </div>
        <div className="rounded-md border border-border bg-bg px-[10px] py-[5px] font-mono text-[10px] text-fg-muted shadow-float">
          {effectiveActive.length > 0
            ? `${effectiveActive.length} suburb${effectiveActive.length !== 1 ? "s" : ""} active`
            : "all suburbs"}
        </div>
      </div>

      <div ref={mapContainerRef} className="liveability-map h-full w-full" />

      {isLoading && (
        <div className="pointer-events-none absolute inset-0 z-[430] grid place-items-center bg-[radial-gradient(circle_at_50%_42%,rgba(255,255,255,0.88),rgba(248,250,252,0.58))] backdrop-blur-[1.5px]">
          <div className="relative flex h-36 w-36 items-center justify-center">
            <span className="absolute h-36 w-36 animate-ping rounded-full border border-blue-300/50" />
            <span className="absolute h-24 w-24 animate-pulse rounded-full border-2 border-indigo-300/80" />
            <span className="rounded-full bg-white/92 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-600 shadow-[0_8px_20px_rgba(15,23,42,0.08)]">
              {loadingLabel}
            </span>
          </div>
        </div>
      )}


      {/* Top 5 — centrado sobre el mapa */}
      {!hideRanking && <div className="pointer-events-none absolute inset-x-0 bottom-6 z-[450] flex justify-center px-3">
        <div className="pointer-events-auto w-full max-w-[600px] overflow-hidden rounded-[12px] border border-border shadow-floatLg backdrop-blur-sm" style={{ background: "radial-gradient(circle at 30% 18%, rgba(254,215,170,0.22), transparent 28%), linear-gradient(180deg,#eff2f8,#e9edf6)" }}>
          <div className="flex items-center gap-1 border-b border-border px-3 py-1.5">
            <span className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-fg-muted">Top suburbs</span>
          </div>
          <div className="flex gap-px overflow-x-auto p-1 scrollbar-none">
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div key={`sk-${i}`} className="w-[108px] animate-pulse rounded-lg p-2.5">
                    <div className="mb-1.5 h-2 w-6 rounded bg-bg-elev" />
                    <div className="mb-2 h-3 w-16 rounded bg-bg-elev" />
                    <div className="h-[3px] rounded bg-bg-elev" />
                  </div>
                ))
              : ranked.filter((s) => s.name).slice(0, 5).map((suburb, index) => {
                  const isActive = activeSet.has(suburb.name.toLowerCase()) || selectedSuburbId === suburb.id;
                  return (
                    <button
                      key={suburb.id}
                      type="button"
                      onClick={() => onSelectSuburb(suburb.name)}
                      className={`w-[108px] cursor-pointer rounded-lg p-2.5 text-left transition hover:-translate-y-0.5 ${
                        isActive ? "bg-fg text-bg" : "text-fg hover:bg-bg-elev"
                      }`}
                    >
                      <div className="flex items-baseline justify-between gap-1">
                        <span className="font-mono text-[9px] opacity-50">#{index + 1}</span>
                        <span className="font-mono text-[12px] font-semibold">{suburb.computedScore}</span>
                      </div>
                      <div className="mt-0.5 truncate text-[11px] font-medium">{suburb.name}</div>
                      <div className="mt-1.5 h-[3px] overflow-hidden rounded-full" style={{ background: isActive ? "rgba(255,255,255,0.18)" : "oklch(0.92 0.005 250)" }}>
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${suburb.computedScore}%`, background: isActive ? "white" : "oklch(0.55 0.18 285)" }}
                        />
                      </div>
                    </button>
                  );
                })}
          </div>
        </div>
      </div>}

    </section>
  );
}
