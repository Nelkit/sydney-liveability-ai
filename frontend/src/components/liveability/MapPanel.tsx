"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Layers3, MapPinned, Shield } from "lucide-react";
import { Suburb, Weights } from "./types";
import { scoreSuburb } from "./utils";

type RankedSuburb = Suburb & { computedScore: number };

type MapPanelProps = {
  suburbs: Suburb[];
  ranked: RankedSuburb[];
  isLoading: boolean;
  selectedSuburbId: string | null;
  onSelectSuburb: (name: string) => void;
  layer: string;
  onLayerChange: (layer: string) => void;
  weights: Weights;
};

const layers = ["Liveability", "Safety", "Transport", "Lifestyle"];
const SMALL_LABEL_MIN_ZOOM = 15;

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
  selectedSuburbId,
  onSelectSuburb,
  layer,
  onLayerChange,
  weights
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const overlaysRef = useRef<L.LayerGroup | null>(null);
  const [suburbsGeoJson, setSuburbsGeoJson] = useState<GeoJSON.FeatureCollection | null>(null);
  const [geoJsonLoaded, setGeoJsonLoaded] = useState(false);
  const [mapZoom, setMapZoom] = useState<number | null>(null);
  const hasFittedBoundsRef = useRef(false);
  const previousLoadingRef = useRef(isLoading);

  const suburbsByName = useMemo(() => {
    const byName = new Map<string, Suburb>();
    suburbs.forEach((suburb) => byName.set(normalizeSuburbName(suburb.name), suburb));
    return byName;
  }, [suburbs]);

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

        if (!cancelled) {
          setSuburbsGeoJson(data);
          setGeoJsonLoaded(true);
        }
      } catch {
        if (!cancelled) {
          setSuburbsGeoJson(null);
          setGeoJsonLoaded(true);
        }
      }
    }

    loadGeoJson();

    return () => {
      cancelled = true;
    };
  }, []);

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

    const overlayGroup = L.layerGroup().addTo(map);

    setMapZoom(map.getZoom());

    const onZoomEnd = () => {
      setMapZoom(map.getZoom());
    };

    map.on("zoomend", onZoomEnd);

    mapRef.current = map;
    overlaysRef.current = overlayGroup;
    hasFittedBoundsRef.current = false;

    return () => {
      map.off("zoomend", onZoomEnd);
      overlayGroup.clearLayers();
      map.remove();
      mapRef.current = null;
      overlaysRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (previousLoadingRef.current && !isLoading) {
      // Re-enable one animated fit when civic data has just finished loading.
      hasFittedBoundsRef.current = false;
    }
    previousLoadingRef.current = isLoading;
  }, [isLoading]);

  useEffect(() => {
    const overlayGroup = overlaysRef.current;
    const map = mapRef.current;
    if (!overlayGroup || !map) return;
    if (!geoJsonLoaded) return;

    overlayGroup.clearLayers();

    if (suburbsGeoJson) {
      // Base layer: render every suburb from GeoJSON with subtle styling.
      const allSuburbsLayer = L.geoJSON(suburbsGeoJson, {
        style: {
          color: "#64748b",
          fillColor: "#64748b",
          fillOpacity: 0.14,
          weight: 0.8,
          opacity: 0.7
        },
        interactive: false
      });

      allSuburbsLayer.addTo(overlayGroup);

      // Highlight layer: only suburbs provided by the backend civic response.
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
          const heatColor = scoreToHeatColor(value);
          const opacity = selectedSuburbId && selectedSuburbId !== suburb.id ? 0.15 : 0.52;
          const isSelected = selectedSuburbId === suburb.id;

          return {
            color: isSelected ? "#f8fafc" : heatColor,
            fillColor: heatColor,
            fillOpacity: opacity,
            weight: isSelected ? 2.2 : 0.8
          };
        },
        onEachFeature: (feature, layerItem) => {
          const featureName = getFeatureSuburbName(feature);
          if (!featureName) return;

          const suburb = suburbsByName.get(featureName);
          if (!suburb) return;

          layerItem.on("click", () => onSelectSuburb(suburb.name));
          if (selectedSuburbId === suburb.id) {
            if ("bringToFront" in layerItem && typeof layerItem.bringToFront === "function") {
              layerItem.bringToFront();
            }
          }
        }
      });

      highlightedLayer.addTo(overlayGroup);

      if (!hasFittedBoundsRef.current && !isLoading) {
        const preferredBounds = highlightedLayer.getBounds();
        if (preferredBounds.isValid()) {
          map.flyToBounds(preferredBounds.pad(0.08), {
            maxZoom: 15,
            duration: 0.9
          });
          hasFittedBoundsRef.current = true;
        }
      }

      if ((mapZoom ?? map.getZoom()) >= SMALL_LABEL_MIN_ZOOM) {
        const visibleBounds = map.getBounds().pad(0.15);

        allSuburbsLayer.eachLayer((layerItem) => {
          const layerWithFeature = layerItem as L.Layer & { feature?: GeoJSON.Feature };
          const feature = layerWithFeature.feature;
          if (!feature) return;

          const normalizedName = getFeatureSuburbName(feature);
          if (!normalizedName) return;
          if (suburbsByName.has(normalizedName)) return;

          if (!("getBounds" in layerItem) || typeof (layerItem as { getBounds?: () => L.LatLngBounds }).getBounds !== "function") {
            return;
          }

          const bounds = (layerItem as { getBounds: () => L.LatLngBounds }).getBounds();
          if (!bounds.isValid()) return;

          const center = bounds.getCenter();
          if (!visibleBounds.contains(center)) return;

          const suburbLabel = getFeatureSuburbLabel(feature);
          if (!suburbLabel) return;

          const smallLabel = L.marker(center, {
            interactive: false,
            keyboard: false,
            icon: L.divIcon({
              className: "suburb-name-label",
              html: `<span style="
                color: #334155;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.01em;
                text-shadow: 0 1px 3px rgba(255,255,255,0.75);
                white-space: nowrap;
                transform: translate(-50%, -50%);
                display: inline-block;
                opacity: 0.9;
              ">${suburbLabel}</span>`
            })
          });

          smallLabel.addTo(overlayGroup);
        });
      }
    } else {
      // Fallback to legacy polygons only if GeoJSON is unavailable.
      suburbs.forEach((suburb) => {
        const value = layerValue(suburb, layer, weights);
        const heatColor = scoreToHeatColor(value);
        const opacity = selectedSuburbId && selectedSuburbId !== suburb.id ? 0.30 : 0.52;
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
      });
    }

    suburbs.forEach((suburb) => {
      const value = layerValue(suburb, layer, weights);
      const heatColor = scoreToHeatColor(value);
      const opacity = selectedSuburbId && selectedSuburbId !== suburb.id ? 0.15 : 0.52;
      const isSelected = selectedSuburbId === suburb.id;

      const circle = L.circle(suburb.center as L.LatLngExpression, {
        radius: 260 + value * 6,
        color: heatColor,
        fillColor: heatColor,
        fillOpacity: opacity * 0.14,
        weight: 0,
        interactive: false,
        bubblingMouseEvents: false
      });

      circle.addTo(overlayGroup);

      const glow = L.circle(suburb.center as L.LatLngExpression, {
        radius: 380 + value * 7,
        color: heatColor,
        fillColor: heatColor,
        fillOpacity: opacity * 0.08,
        weight: 0,
        interactive: false,
        bubblingMouseEvents: false
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
    });
  }, [suburbs, suburbsByName, suburbsGeoJson, geoJsonLoaded, mapZoom, layer, weights, selectedSuburbId, onSelectSuburb, isLoading]);

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

      {isLoading ? (
        <div className="pointer-events-none absolute inset-0 z-[430] grid place-items-center bg-[radial-gradient(circle_at_50%_42%,rgba(255,255,255,0.88),rgba(248,250,252,0.58))] backdrop-blur-[1.5px]">
          <div className="relative flex h-36 w-36 items-center justify-center">
            <span className="absolute h-36 w-36 animate-ping rounded-full border border-blue-300/50" />
            <span className="absolute h-24 w-24 animate-pulse rounded-full border-2 border-indigo-300/80" />
            <span className="rounded-full bg-white/92 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-600 shadow-[0_8px_20px_rgba(15,23,42,0.08)]">
              Loading civic data
            </span>
          </div>
        </div>
      ) : null}

      <div className="pointer-events-none absolute bottom-6 right-3 z-[450] rounded-xl border border-white/70 bg-white/86 p-2 shadow-[0_10px_28px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="mb-1 flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.06em] text-slateMuted">
          <Layers3 size={10} />
          {layer} heat scale
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium text-slate-500">Cold</span>
          <div className="h-2 w-24 rounded-full bg-gradient-to-r from-blue-500 via-orange-500 to-red-500" />
          <span className="text-[10px] font-medium text-slate-500">Hot</span>
        </div>
      </div>

      <div className="scrollbar-none absolute inset-x-0 bottom-0 z-[450] flex gap-2 overflow-x-auto bg-gradient-to-t from-slate-900/20 via-slate-900/5 to-transparent pb-3 pl-2 pr-3 pt-6 md:pl-[370px]">
        {isLoading
          ? Array.from({ length: 5 }).map((_, index) => (
              <div
                key={`loading-card-${index}`}
                className="min-w-[146px] flex-shrink-0 animate-pulse rounded-2xl border border-white/85 bg-white/80 p-3 shadow-[0_10px_24px_rgba(15,23,42,0.08)] backdrop-blur"
              >
                <div className="mb-2 flex items-start justify-between">
                  <div className="space-y-1.5">
                    <div className="h-2 w-8 rounded bg-slate-200" />
                    <div className="h-3 w-20 rounded bg-slate-300" />
                  </div>
                  <div className="h-8 w-10 rounded bg-slate-300" />
                </div>
                <div className="h-1 rounded bg-slate-200">
                  <div className="h-1 w-2/3 rounded bg-slate-300" />
                </div>
              </div>
            ))
          : ranked.map((suburb, index) => (
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
