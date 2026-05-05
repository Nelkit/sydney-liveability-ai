"use client";

import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { Coffee, PanelRight, Plus, Shield, TrainFront } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AssistantSidebar } from "../components/liveability/AssistantSidebar";
import { importanceOptions, quickChips, suburbs, weightPrompts } from "../components/liveability/data";
import { ImportanceSlider } from "../components/liveability/ImportanceSlider";
import { OnboardingPanel } from "../components/liveability/OnboardingPanel";
import { ReportModal } from "../components/liveability/ReportModal";
import { SharedBrand } from "../components/liveability/SharedBrand";
import { ChatMessage, ImportanceLevelKey, Weights, Suburb } from "../components/liveability/types";
import { scoreSuburb } from "../components/liveability/utils";
import {
  AssistantBubble,
  AssistantBubbleSkeleton,
  OutOfScopeState,
  TypingBubble,
  UserBubble,
} from "../components/liveability/ChatBubbles";
import { ChatInput } from "../components/liveability/ChatInput";
import { EvidenceDrawer } from "../components/liveability/EvidenceDrawer";
import { CitationHoverProvider } from "../context/CitationHoverContext";
import type {
  AssistantMessage,
  ChatAPIResponse,
  Citation,
  Claim,
  EvidenceTrace,
  RouterCategory,
  RouterMeta,
  SourceKind,
} from "../types/api";

const MapPanel = dynamic(
  () => import("../components/liveability/MapPanel").then((m) => m.MapPanel),
  { ssr: false }
);

const initialWeights: Weights = { transport: 0, safety: 0, lifestyle: 0, afford: 0, proximity: 0 };
const API_BASE_URL   = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const CIVIC_ENDPOINT = `${API_BASE_URL}/api/civic`;
const PREFERENCES_STORAGE_KEY = "sydney-liveability-preferences-v1";
const USER_WEIGHTS_STORAGE_KEY = "user_weights";
const CANCEL_SHOW_DELAY_MS = 3000;
const MAP_LAYERS = ["Liveability", "Safety", "Transport", "Lifestyle"] as const;
const MAP_LAYER_MAP: Record<string, (typeof MAP_LAYERS)[number]> = {
  liveability: "Liveability",
  safety: "Safety",
  transport: "Transport",
  lifestyle: "Lifestyle",
};
const SOURCE_KIND_LIST: SourceKind[] = ["reddit", "bocsar", "arcgis", "osm", "tfnsw", "pdf"];

// ---------- helpers ----------

function getUserWeights() {
  const defaults = { transport: 0.25, safety: 0.25, lifestyle: 0.25, affordability: 0.25, nightlife: 0.0, proximity: 0.0 };
  const importanceValueMap: Record<string, number> = Object.fromEntries(importanceOptions.map((o) => [o.key, o.value]));
  try {
    const stored = window.localStorage.getItem(USER_WEIGHTS_STORAGE_KEY);
    if (!stored) return defaults;
    const prefs = JSON.parse(stored) as Record<string, string>;
    const keys = ["transport", "safety", "lifestyle", "affordability", "nightlife", "proximity"] as const;
    const raw = {
      transport: importanceValueMap[prefs.transport] ?? 50,
      safety: importanceValueMap[prefs.safety] ?? 50,
      lifestyle: importanceValueMap[prefs.lifestyle] ?? 50,
      affordability: importanceValueMap[prefs.affordability] ?? 50,
      nightlife: 0,
      proximity: importanceValueMap[prefs.proximity] ?? 0,
    } satisfies Record<(typeof keys)[number], number>;
    const total = Object.values(raw).reduce((a, b) => a + b, 0);
    if (!total) return defaults;
    return Object.fromEntries(keys.map((k) => [k, parseFloat((raw[k] / total).toFixed(4))])) as typeof defaults;
  } catch { return defaults; }
}

function getImportanceScore(k: ImportanceLevelKey) {
  return importanceOptions.find((o) => o.key === k)?.value ?? 50;
}
function getImportanceLabel(k?: ImportanceLevelKey) {
  if (!k) return "Unset";
  return importanceOptions.find((o) => o.key === k)?.label ?? "Unset";
}

type CivicGeometry  = { type: string; coordinates: unknown };
type CivicProperties= { suburb: string; sa4_area: string; liveability_score: number; safety_score: number; transport_score: number; lifestyle_score: number; nightlife_score: number; proximity_score: number };
type CivicFeature   = { type: "Feature"; properties: CivicProperties; geometry: CivicGeometry | Record<string, never> };
type CivicResponse  = { type: "FeatureCollection"; features: CivicFeature[] };

function extractCenterAndPolygon(geometry: CivicGeometry | Record<string, never>) {
  const fallback = { center: [-33.8688, 151.2093] as [number, number], polygon: [] as [number, number][] };
  if (!geometry || !("type" in geometry) || geometry.type !== "MultiPolygon" || !Array.isArray(geometry.coordinates)) return fallback;
  try {
    const outerRing = ((geometry.coordinates as unknown[][][])[0] as unknown[][])[0] as unknown[][];
    if (!Array.isArray(outerRing) || !outerRing.length) return fallback;
    const polygonCoords = outerRing
      .filter((c) => Array.isArray(c) && c.length >= 2 && isFinite(c[0] as number) && isFinite(c[1] as number))
      .map((c) => [c[1], c[0]] as [number, number]);
    if (!polygonCoords.length) return fallback;
    const sumLat = polygonCoords.reduce((s, [lat]) => s + lat, 0);
    const sumLng = polygonCoords.reduce((s, [, lng]) => s + lng, 0);
    const center: [number, number] = [sumLat / polygonCoords.length, sumLng / polygonCoords.length];
    if (!isFinite(center[0]) || !isFinite(center[1])) return fallback;
    return { center, polygon: polygonCoords };
  } catch { return fallback; }
}

function civicToSuburbs(data: CivicResponse): Suburb[] {
  const colorMap: Record<string, string> = { newtown: "#3b82f6", glebe: "#10b981", redfern: "#f59e0b", "surry hills": "#8b5cf6", haymarket: "#ef4444" };
  return data.features.flatMap((f) => {
    const { suburb, liveability_score, safety_score, transport_score, lifestyle_score, proximity_score } = f.properties;
    if (!suburb) return [];
    const { center, polygon } = extractCenterAndPolygon(f.geometry);
    return [{
      id: suburb.toLowerCase().replace(/\s+/g, "-"),
      name: suburb,
      color: colorMap[suburb.toLowerCase()] ?? "#6366f1",
      scoreBase: {
        transport: Math.round(transport_score * 100),
        safety: Math.round(safety_score * 100),
        lifestyle: Math.round(lifestyle_score * 100),
        afford: 50,
        proximity: Math.round((proximity_score ?? 0.5) * 100),
      },
      center, polygon,
    }];
  });
}

// Minimal parser: keep markdown intact when present
function parseAnswerToClaims(answer: string): Claim[] {
  const hasMarkdown = /\n|^\s*[-*]\s+|\*\*|^>\s+/m.test(answer);
  if (hasMarkdown) {
    return [{ text: answer, cites: [] }];
  }
  return answer.split(/(?<=[.!?])\s+/).filter(Boolean).map((text) => ({ text, cites: [] }));
}

type SourceObject = { source?: SourceKind; suburb?: string; text?: string };

function isSourceKind(value: unknown): value is SourceKind {
  return typeof value === "string" && SOURCE_KIND_LIST.includes(value as SourceKind);
}

function isSourceObject(value: unknown): value is SourceObject {
  return typeof value === "object" && value !== null && ("source" in value || "suburb" in value || "text" in value);
}

function sourceDetail(kind: SourceKind, suburbs: string[]) {
  if (!suburbs.length) return `Source: ${kind}`;
  if (suburbs.length === 1) return `${suburbs[0]} · ${kind}`;
  return `${suburbs.join(", ")} · ${kind}`;
}

function normalizeSourcesToCitations(
  payload: ChatAPIResponse,
  router: { suburbs: string[] }
): Citation[] {
  const raw: unknown[] = Array.isArray(payload.sources) ? (payload.sources as unknown[]) : [];
  if (!raw.length) return [];
  const citations: Citation[] = [];
  let n = 1;

  raw.forEach((item) => {
    if (isSourceKind(item)) {
      const detail = sourceDetail(item, router.suburbs);
      citations.push({ n: n++, src: item, suburbs: router.suburbs, detail });
      return;
    }

    if (isSourceObject(item)) {
      const kind = isSourceKind(item.source) ? item.source : null;
      if (!kind) return;
      const suburbs = item.suburb ? [item.suburb] : router.suburbs;
      const detail = item.text ? item.text : sourceDetail(kind, suburbs);
      citations.push({ n: n++, src: kind, suburbs, detail });
    }
  });

  return citations;
}

function buildClaimsWithCitations(
  payload: ChatAPIResponse,
  router: { suburbs: string[] }
): Claim[] {
  const claims = payload.claims ? payload.claims : parseAnswerToClaims(payload.answer ?? "");
  const hasCites = claims.some((cl) => cl.cites && cl.cites.length > 0);
  if (hasCites) return claims;

  const citations = normalizeSourcesToCitations(payload, router);
  if (!citations.length) return claims;

  return claims.map((cl, idx) => ({
    ...cl,
    cites: [citations[idx % citations.length]],
  }));
}

// Convert old-style ChatApiResponse to AssistantMessage
function normalizeRouter(payload: ChatAPIResponse, fallbackSuburb: string | null): AssistantMessage["router"] {
  const raw = payload.router as (RouterMeta & { suburbs_mentioned?: string[] }) | undefined;
  const suburbs = Array.isArray(raw?.suburbs)
    ? raw.suburbs
    : Array.isArray(raw?.suburbs_mentioned)
      ? raw.suburbs_mentioned
      : fallbackSuburb
        ? [fallbackSuburb]
        : [];

  return {
    categories: Array.isArray(raw?.categories) ? raw.categories : (["sentiment"] as RouterCategory[]),
    suburbs,
    latencyMs: typeof raw?.latencyMs === "number" ? raw.latencyMs : 0,
  };
}

function apiResponseToAssistantMessage(payload: ChatAPIResponse, suburb: string | null): AssistantMessage {
  const router = normalizeRouter(payload, suburb);

  const isOutOfScope = router.categories.includes("out_of_scope");

  const claims: Claim[] = buildClaimsWithCitations(payload, router);

  // Collect all citations for evidence drawer
  const sources = Array.isArray(payload.sources) ? payload.sources : [];

  const summary = !isOutOfScope && router.suburbs.length > 0
    ? { suburbs: router.suburbs }
    : undefined;

  return {
    role: "assistant",
    ts: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    router,
    claims: isOutOfScope ? [] : claims,
    summary,
  };
}

// ---------- types ----------

type StoredPreferences = { weights: Weights; selectedLevels: Partial<Record<keyof Weights, ImportanceLevelKey>>; profileReady: boolean };

type DisplayMessage =
  | { type: "user"; text: string; ts: string }
  | { type: "assistant"; message: AssistantMessage; payload: ChatAPIResponse; suburb: string | null }
  | { type: "out_of_scope" }
  | { type: "typing"; step?: string };

// ---------- component ----------

export default function HomePage() {
  const [isHydrated, setIsHydrated]   = useState(false);
  const [isAppOpen,  setIsAppOpen]    = useState(false);
  const [weights,    setWeights]      = useState<Weights>(initialWeights);
  const [selectedLevels, setSelectedLevels] = useState<Partial<Record<keyof Weights, ImportanceLevelKey>>>({});
  const [draftLevels,    setDraftLevels]    = useState<Partial<Record<keyof Weights, ImportanceLevelKey>>>({});
  const [profileReady,   setProfileReady]   = useState(false);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [onboardingMessages,   setOnboardingMessages]   = useState<ChatMessage[]>([]);
  const [onboardingTyping,     setOnboardingTyping]     = useState(false);

  const [selectedSuburbId, setSelectedSuburbId] = useState<string | null>(null);
  const [layer,    setLayer]    = useState("Liveability");
  const [chatInput, setChatInput] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [civicData,   setCivicData]   = useState<CivicResponse | null>(null);
  const [isCivicLoading, setIsCivicLoading] = useState(true);
  const [civicLoadingLabel, setCivicLoadingLabel] = useState("Loading civic data");
  const [hoveredSuburb,  setHoveredSuburb]  = useState<string | null>(null);

  const [reportModal, setReportModal] = useState<{ mode: "single" | "compare"; suburbs: string[] } | null>(null);

  const [displayMessages, setDisplayMessages] = useState<DisplayMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [showEvidence, setShowEvidence] = useState(true);
  const [mobileTab, setMobileTab] = useState<"chat" | "map" | "evidence">("chat");
  const [chatActiveSuburbs, setChatActiveSuburbs] = useState<string[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const cancelTimerRef     = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chatScrollRef      = useRef<HTMLDivElement | null>(null);
  const popoverRef         = useRef<HTMLDivElement | null>(null);

  // Latest payload for EvidenceDrawer
  const [lastPayload, setLastPayload] = useState<ChatAPIResponse | null>(null);
  // Per-suburb payload cache — keyed by lowercase suburb name
  const [suburbPayloads, setSuburbPayloads] = useState<Record<string, ChatAPIResponse>>({});
  const allCitations = useMemo<Citation[]>(() => {
    if (!lastPayload?.claims) return [];
    return lastPayload.claims.flatMap((cl) => cl.cites);
  }, [lastPayload]);

  // Active suburbs for map — prefer explicit map_state from last payload, fallback to last assistant router
  const activeSuburbs = useMemo<string[]>(() => {
    if (lastPayload?.map_state?.activeSuburbs && lastPayload.map_state.activeSuburbs.length > 0) {
      return lastPayload.map_state.activeSuburbs;
    }
    const last = [...displayMessages].reverse().find((m) => m.type === "assistant");
    if (!last || last.type !== "assistant") return [];
    return last.message.router.suburbs;
  }, [displayMessages, lastPayload]);

  const allSuburbsForMap = useMemo(() => {
    return civicData ? civicToSuburbs(civicData) : suburbs;
  }, [civicData]);

  const rankedSuburbs = useMemo(() => {
    if (civicData) {
      return civicData.features.map((f, i) => {
        const s = civicToSuburbs(civicData)[i];
        return { ...s, computedScore: Math.round(f.properties.liveability_score * 100) };
      });
    }
    return allSuburbsForMap.map((s) => ({ ...s, computedScore: scoreSuburb(s, weights) })).sort((a, b) => b.computedScore - a.computedScore);
  }, [weights, civicData, allSuburbsForMap]);

  const mapWeights = useMemo<Weights>(() => {
    const heat = lastPayload?.map_state?.heatmap_weights;
    if (!heat || Object.keys(heat).length === 0) return weights;
    return {
      transport: typeof heat.transport === "number" ? heat.transport : weights.transport,
      safety: typeof heat.safety === "number" ? heat.safety : weights.safety,
      lifestyle: typeof heat.lifestyle === "number" ? heat.lifestyle : weights.lifestyle,
      afford: weights.afford,
      proximity: weights.proximity,
    };
  }, [lastPayload, weights]);

  useEffect(() => {
    const rawLayer = lastPayload?.map_state?.layer;
    if (!rawLayer) return;
    const normalized = MAP_LAYER_MAP[rawLayer.toLowerCase()] ?? rawLayer;
    if (MAP_LAYERS.includes(normalized as (typeof MAP_LAYERS)[number])) {
      setLayer(normalized);
    }
  }, [lastPayload]);

  useEffect(() => {
    const nextActive = lastPayload?.map_state?.activeSuburbs ?? [];
    if (!nextActive.length) return;
    const detected = allSuburbsForMap.find((s) =>
      s.name.toLowerCase() === nextActive[0].toLowerCase()
    );
    if (detected) setSelectedSuburbId(detected.id);
  }, [allSuburbsForMap, lastPayload]);

  // Hydrate from storage
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PREFERENCES_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as StoredPreferences;
        if (parsed.profileReady) {
          setWeights({ ...initialWeights, ...parsed.weights });
          setSelectedLevels(parsed.selectedLevels);
          setProfileReady(true);
          setIsAppOpen(true);
        }
      }
    } catch { /* ignore */ } finally { setIsHydrated(true); }
  }, []);

  // Persist weights
  useEffect(() => {
    if (!isHydrated || !profileReady) return;
    window.localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify({ weights, selectedLevels, profileReady: true }));
    window.localStorage.setItem(USER_WEIGHTS_STORAGE_KEY, JSON.stringify({
      transport: getImportanceLabel(selectedLevels.transport),
      safety:    getImportanceLabel(selectedLevels.safety),
      lifestyle: getImportanceLabel(selectedLevels.lifestyle),
      affordability: getImportanceLabel(selectedLevels.afford),
      nightlife: "Neutral",
      proximity: getImportanceLabel(selectedLevels.proximity),
    }));
  }, [isHydrated, profileReady, weights, selectedLevels]);

  // Load civic data — only after profile is ready (all 5 weights selected).
  // During onboarding selectedLevels changes 5 times; we must not fetch until done.
  useEffect(() => {
    if (!isHydrated || !profileReady) return;
    setIsCivicLoading(true);
    const importanceValueMap: Record<string, number> = Object.fromEntries(
      importanceOptions.map((o) => [o.key, o.value])
    );
    const raw = {
      transport:     importanceValueMap[selectedLevels.transport     ?? ""] ?? 50,
      safety:        importanceValueMap[selectedLevels.safety        ?? ""] ?? 50,
      lifestyle:     importanceValueMap[selectedLevels.lifestyle     ?? ""] ?? 50,
      affordability: importanceValueMap[selectedLevels.afford        ?? ""] ?? 50,
      nightlife:     0,
      proximity:     importanceValueMap[selectedLevels.proximity     ?? ""] ?? 0,
    };
    const total = Object.values(raw).reduce((a, b) => a + b, 0) || 1;
    const civicWeights = Object.fromEntries(
      Object.entries(raw).map(([k, v]) => [k, parseFloat((v / total).toFixed(4))])
    );
    const params = new URLSearchParams(
      Object.entries(civicWeights).map(([k, v]) => [k, String(v)])
    );
    fetch(`${CIVIC_ENDPOINT}?${params}`)
      .then((r) => r.ok ? r.json() as Promise<CivicResponse> : Promise.reject())
      .then(setCivicData)
      .catch(() => {})
      .finally(() => {
        setIsCivicLoading(false);
        setCivicLoadingLabel("Loading civic data");
      });
  }, [isHydrated, profileReady, selectedLevels]);

  // Popover close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) setProfileOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Welcome message when app opens
  useEffect(() => {
    if (!isAppOpen) return;
    setDisplayMessages([]);
  }, [isAppOpen]);

  // Auto-show profile panel briefly — only when transitioning FROM onboarding, not on page refresh
  function openAppFromOnboarding() {
    setIsAppOpen(true);
    setProfileOpen(true);
    setTimeout(() => setProfileOpen(false), 4000);
  }

  // Sync draft from committed state whenever the popover opens
  useEffect(() => {
    if (profileOpen) setDraftLevels(selectedLevels);
  }, [profileOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll chat
  useEffect(() => {
    chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
  }, [displayMessages]);

  function applyWeightChoice(key: keyof Weights, choiceKey: ImportanceLevelKey) {
    setWeights((prev) => ({ ...prev, [key]: getImportanceScore(choiceKey) }));
    setSelectedLevels((prev) => ({ ...prev, [key]: choiceKey }));
  }

  function handleOnboardingChoice(choiceKey: ImportanceLevelKey) {
    if (profileReady) return;
    const prompt = weightPrompts[currentQuestionIndex];
    setOnboardingMessages((prev) => [...prev, { role: "user", html: `${prompt.label}: ${getImportanceLabel(choiceKey)}` }]);
    applyWeightChoice(prompt.key, choiceKey);
    const next = currentQuestionIndex + 1;
    if (next < weightPrompts.length) {
      setCurrentQuestionIndex(next);
      setOnboardingTyping(true);
      setTimeout(() => {
        setOnboardingTyping(false);
        setOnboardingMessages((prev) => [...prev, { role: "ai", html: `Perfect. ${weightPrompts[next].prompt}` }]);
      }, 420);
    } else {
      setProfileReady(true);
      setOnboardingMessages((prev) => [...prev, { role: "ai", html: "Excellent, we have captured your profile. You can fine-tune each category using the same choice levels and then continue to the map." }]);
    }
  }

  function cancelRequest() {
    abortControllerRef.current?.abort();
    if (cancelTimerRef.current) clearTimeout(cancelTimerRef.current);
    setIsLoading(false);
    setShowCancel(false);
    setDisplayMessages((prev) => prev.filter((m) => m.type !== "typing"));
  }

  async function sendChat(text?: string, suburbOverride?: string) {
    const value = (text ?? chatInput).trim();
    if (!value || isLoading) return;

    const activeSuburbName = suburbOverride
      ?? allSuburbsForMap.find((s) => s.id === selectedSuburbId)?.name
      ?? null;

    // Detect suburbs in user message immediately — zoom + highlight before API responds
    const valueLower = value.toLowerCase();
    const mentionedSuburbs = allSuburbsForMap.filter((s) => valueLower.includes(s.name.toLowerCase())).map((s) => s.name);
    if (mentionedSuburbs.length > 0) setChatActiveSuburbs(mentionedSuburbs);

    const messageToSend = value;

    setChatInput("");
    setIsLoading(true);
    setShowCancel(false);

    setDisplayMessages((prev) => [
      ...prev,
      { type: "user", text: value, ts: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) },
      { type: "typing" },
    ]);

    // Show cancel button after CANCEL_SHOW_DELAY_MS
    cancelTimerRef.current = setTimeout(() => setShowCancel(true), CANCEL_SHOW_DELAY_MS);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageToSend, weights: getUserWeights() }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`API error ${res.status}`);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      outer: while (true) {
        const { done, value: chunk } = await reader.read();
        if (done) break;
        buffer += decoder.decode(chunk, { stream: true });

        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const eventMatch = block.match(/^event: (\w+)/m);
          const dataMatch  = block.match(/^data: (.+)/m);
          if (!eventMatch || !dataMatch) continue;

          const eventType = eventMatch[1];
          const data = JSON.parse(dataMatch[1]);

          if (eventType === "step") {
            setDisplayMessages((prev) => [
              ...prev.filter((m) => m.type !== "typing"),
              { type: "typing", step: data.text as string },
            ]);
          } else if (eventType === "error") {
            setDisplayMessages((prev) => [
              ...prev.filter((m) => m.type !== "typing"),
              {
                type: "assistant",
                message: {
                  role: "assistant",
                  ts: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                  router: { categories: ["sentiment"], suburbs: [], latencyMs: 0 },
                  claims: [{ text: data.message ?? "I could not process that question right now.", cites: [] }],
                },
                payload: { answer: "", sources: [] },
                suburb: activeSuburbName,
              },
            ]);
            break outer;
          } else if (eventType === "done") {
            const payload = data as ChatAPIResponse;
            const message = apiResponseToAssistantMessage(payload, activeSuburbName);
            const isOutOfScope = message.router.categories.includes("out_of_scope");
            const hydratedPayload: ChatAPIResponse = payload.claims
              ? payload
              : { ...payload, claims: message.claims };

            setLastPayload(hydratedPayload);
            if (message.router.suburbs.length > 0) {
              setSuburbPayloads((prev) => {
                const next = { ...prev };
                for (const s of message.router.suburbs) next[s.toLowerCase()] = hydratedPayload;
                return next;
              });
            }
            setDisplayMessages((prev) => [
              ...prev.filter((m) => m.type !== "typing"),
              isOutOfScope
                ? { type: "out_of_scope" }
                : { type: "assistant", message, payload: hydratedPayload, suburb: activeSuburbName },
            ]);
            if (message.router.suburbs.length > 0) {
              const detected = allSuburbsForMap.find((s) =>
                s.name.toLowerCase() === message.router.suburbs[0].toLowerCase()
              );
              if (detected) setSelectedSuburbId(detected.id);
              setChatActiveSuburbs(message.router.suburbs);
            }
            break outer;
          }
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setDisplayMessages((prev) => [
        ...prev.filter((m) => m.type !== "typing"),
        {
          type: "assistant",
          message: {
            role: "assistant",
            ts: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            router: { categories: ["sentiment"], suburbs: [], latencyMs: 0 },
            claims: [{ text: "I could not process that question right now. Please try again.", cites: [] }],
          },
          payload: { answer: "", sources: [] },
          suburb: activeSuburbName,
        },
      ]);
    } finally {
      if (cancelTimerRef.current) clearTimeout(cancelTimerRef.current);
      setIsLoading(false);
      setShowCancel(false);
    }
  }

  function onSelectSuburb(name: string) {
    const sub = allSuburbsForMap.find((s) => s.name === name);
    if (sub) setSelectedSuburbId(sub.id);
    setMobileTab("chat");
    void sendChat(`Tell me about ${name}`, name);
  }


  function resetPreferences() {
    window.localStorage.removeItem(PREFERENCES_STORAGE_KEY);
    window.localStorage.removeItem(USER_WEIGHTS_STORAGE_KEY);
    setWeights(initialWeights);
    setSelectedLevels({});
    setProfileReady(false);
    setCurrentQuestionIndex(0);
    setOnboardingMessages([]);
    setIsAppOpen(false);
    setDisplayMessages([]);
    setSelectedSuburbId(null);
    setLastPayload(null);
  }

  if (!isHydrated) return <main className="h-screen bg-bg" />;

  return (
    <CitationHoverProvider>
      <LayoutGroup>
        <main className="h-screen overflow-hidden">
          <AnimatePresence mode="sync" initial={false}>
            {!isAppOpen ? (
              <OnboardingPanel
                key="onboarding"
                messages={onboardingMessages}
                typing={onboardingTyping}
                onSelectOnboardingChoice={handleOnboardingChoice}
                weights={weights}
                profileReady={profileReady}
                selectedLevels={selectedLevels}
                onWeightLevelChange={applyWeightChoice}
                onBack={() => {
                  setOnboardingMessages([]);
                  setOnboardingTyping(false);
                  setCurrentQuestionIndex(0);
                  setSelectedLevels({});
                }}
                onContinue={profileReady ? () => openAppFromOnboarding() : () => {
                  setOnboardingTyping(true);
                  setTimeout(() => {
                    setOnboardingTyping(false);
                    setOnboardingMessages([
                      { role: "ai", html: "Hi, I am your <strong>Sydney Liveability AI</strong>. Let us build your weighting profile in a conversational way." },
                      { role: "ai", html: weightPrompts[0].prompt },
                    ]);
                  }, 400);
                }}
              />
            ) : (
              <motion.section
                key="main-app"
                initial={{ opacity: 0, scale: 0.992, y: 14 }}
                animate={{ opacity: 1, scale: 1, y: 0, transition: { duration: 0.46, ease: [0.22, 1, 0.36, 1], delay: 0.02 } }}
                exit={{ opacity: 0, scale: 1.006, y: -8, transition: { duration: 0.26, ease: [0.4, 0, 1, 1] } }}
                className="flex h-screen flex-col bg-bg lg:grid lg:grid-rows-[52px_1fr]"
              >
                {/* ---- HEADER ---- */}
                <header className="relative z-[700] flex shrink-0 items-center gap-3 border-b border-border bg-bg px-4 lg:px-5">
                  <motion.div layoutId="top-shell">
                    <SharedBrand compact />
                  </motion.div>
                  <div className="h-5 w-px bg-border" />
                  <span className="font-mono text-[10px] text-fg-muted border border-border rounded px-1.5 py-px">{`v${process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0"}`}</span>

                  <div ref={popoverRef} className="relative">
                    <button
                      type="button"
                      onClick={() => setProfileOpen((p) => !p)}
                      className="inline-flex flex-nowrap items-center justify-center gap-1 rounded-full border border-border bg-bg px-2 py-1 whitespace-nowrap shadow-float"
                    >
                      <span className="inline-flex h-6 items-center justify-center font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-fg">MY PROFILE</span>
                      {[
                        { icon: <TrainFront size={10} />, key: "transport" as const },
                        { icon: <Shield    size={10} />, key: "safety"    as const },
                        { icon: <Coffee    size={10} />, key: "lifestyle" as const },
                      ].map(({ icon, key }) => (
                        <span key={key} className="hidden sm:inline-flex h-6 items-center gap-1 rounded-full border border-border bg-bg-elev px-2 font-mono text-[10px] font-semibold text-fg">
                          {icon} {getImportanceLabel(selectedLevels[key])}
                        </span>
                      ))}
                    </button>

                    {profileOpen && (
                      <motion.div
                        layoutId="profile-card"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="absolute left-0 top-[calc(100%+8px)] z-[900] rounded-b-[10px] border border-border p-4 shadow-float"
                        style={{
                          width: "min(calc(100vw - 1rem), 780px)",
                          background: "radial-gradient(circle at 30% 18%, rgba(254,215,170,0.22), transparent 28%), linear-gradient(180deg,#eff2f8,#e9edf6)",
                        }}
                      >
                        <p className="mb-3 font-mono text-[11px] font-bold uppercase tracking-[0.07em] text-fg-muted">
                          Adjust weighting profile
                        </p>
                        <div className="w-full min-w-0 sm:min-w-[620px] sm:max-w-[760px] space-y-0">
                          {([ ["transport", "Transport"], ["safety", "Safety"], ["lifestyle", "Lifestyle"], ["afford", "Affordability"], ["proximity", "CBD Proximity"] ] as [keyof Weights, string][]).map(([key, label], i, arr) => (
                            <div key={key} className={i < arr.length - 1 ? "mb-4 border-b border-border pb-4" : ""}>
                              <span className="mb-2 block text-sm font-semibold text-fg">{label}</span>
                              <ImportanceSlider
                                value={draftLevels[key]}
                                onChange={(k) => setDraftLevels((prev) => ({ ...prev, [key]: k }))}
                              />
                            </div>
                          ))}
                        </div>
                        <div className="mt-4 flex gap-2">
                          <button
                            type="button"
                            onClick={resetPreferences}
                            className="rounded-full border border-border px-3 py-2 text-xs font-semibold text-fg transition hover:border-fg"
                          >
                            Reset
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setCivicLoadingLabel("Updating weights…");
                              (Object.entries(draftLevels) as [keyof Weights, ImportanceLevelKey][]).forEach(
                                ([key, val]) => { if (val) applyWeightChoice(key, val); }
                              );
                              setProfileOpen(false);
                            }}
                            className="flex-1 rounded-full bg-fg px-3 py-2 text-xs font-semibold text-bg transition hover:opacity-90"
                          >
                            Apply
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </div>


                  <div className="ml-auto flex items-center gap-2">
                    <button
                      type="button"
                      title={showEvidence ? "Hide evidence trail" : "Show evidence trail"}
                      onClick={() => setShowEvidence((v) => !v)}
                      className={`flex size-7 items-center justify-center rounded-md border transition ${showEvidence ? "border-accent bg-accent/10 text-accent" : "border-border bg-bg text-fg hover:bg-bg-elev"}`}
                    >
                      <PanelRight size={13} strokeWidth={1.4} />
                    </button>
                    <button type="button" title="New chat" onClick={() => { setDisplayMessages([]); setChatActiveSuburbs([]); }} className="flex size-7 items-center justify-center rounded-md border border-border bg-bg text-fg transition hover:bg-bg-elev">
                      <Plus size={13} strokeWidth={1.4} />
                    </button>
                  </div>
                </header>

                {/* ---- CONTENT ROW: tab bar (mobile) + columns ---- */}
                <div className={`flex min-h-0 flex-1 flex-col lg:grid ${showEvidence ? "lg:grid-cols-[440px_1fr_320px]" : "lg:grid-cols-[440px_1fr]"}`}>

                  {/* Mobile tab bar — shrink-0 so it never grows, only visible on small screens */}
                  <div className="flex shrink-0 border-b border-border bg-bg lg:hidden">
                    {(["chat", "map", ...(showEvidence ? ["evidence"] : [])] as ("chat" | "map" | "evidence")[]).map((tab) => (
                      <button
                        key={tab}
                        type="button"
                        onClick={() => setMobileTab(tab)}
                        className={`flex-1 py-2 font-mono text-[11px] uppercase tracking-[0.06em] transition ${mobileTab === tab ? "border-b-2 border-accent text-accent" : "text-fg-muted hover:text-fg"}`}
                      >
                        {tab}
                      </button>
                    ))}
                  </div>
                  {/* COL 1: CHAT */}
                  <div className={`flex min-h-0 flex-col border-r border-border ${mobileTab !== "chat" ? "hidden lg:flex" : "flex flex-1"}`} style={{ background: "radial-gradient(circle at 30% 18%, rgba(254,215,170,0.22), transparent 28%), linear-gradient(180deg,#eff2f8,#e9edf6)" }}>
                    <div
                      ref={chatScrollRef}
                      className="flex flex-1 flex-col gap-[18px] overflow-auto px-6 py-5"
                    >
                      {displayMessages.length === 0 && (
                        <div className="flex max-w-[90%] flex-col gap-1.5 self-start">
                          <div className="rounded-[6px_16px_16px_16px] border border-border bg-bg px-4 py-3 text-sm leading-relaxed text-fg shadow-float backdrop-blur">
                            Welcome to Sydney Liveability AI. Ask me about any suburb — transport links, safety, lifestyle vibes, or compare two areas side by side.
                          </div>
                          <div className="font-mono text-[10px] text-fg-muted">assistant</div>
                        </div>
                      )}

                      {displayMessages.map((m, i) => {
                        if (m.type === "user")       return <UserBubble key={i} text={m.text} ts={m.ts} />;
                        if (m.type === "typing")     return <TypingBubble key={i} step={m.step} />;
                        if (m.type === "out_of_scope") return <OutOfScopeState key={i} onSuburbClick={(t) => sendChat(t)} />;
                        if (m.type === "assistant") {
                          return (
                            <AssistantBubble
                              key={i}
                              message={m.message}
                              onOpenReport={(suburbs) => {
                                setReportModal({
                                  mode: suburbs.length >= 2 ? "compare" : "single",
                                  suburbs,
                                });
                              }}
                            />
                          );
                        }
                        return null;
                      })}
                    </div>

                    <ChatInput
                      value={chatInput}
                      onChange={setChatInput}
                      onSend={() => sendChat()}
                      isLoading={isLoading}
                      onCancel={showCancel ? cancelRequest : undefined}
                    />
                  </div>

                  {/* COL 2: MAP — never display:none so Leaflet always has a real size */}
                  <div className={`relative min-h-0 ${mobileTab !== "map" ? "invisible pointer-events-none absolute inset-0 lg:visible lg:pointer-events-auto lg:static" : "flex-1"}`}>
                    <MapPanel
                      suburbs={allSuburbsForMap}
                      ranked={rankedSuburbs}
                      isLoading={isCivicLoading}
                      loadingLabel={civicLoadingLabel}
                      selectedSuburbId={selectedSuburbId}
                      onSelectSuburb={onSelectSuburb}
                      layer={layer}
                      onLayerChange={setLayer}
                      weights={mapWeights}
                      activeSuburbs={chatActiveSuburbs}
                      hoveredSuburb={hoveredSuburb}
                      onSuburbHover={setHoveredSuburb}
                      isVisible={mobileTab === "map"}
                    />
                  </div>

                  {/* COL 3: EVIDENCE DRAWER */}
                  {showEvidence && (
                    <div className={`min-h-0 ${mobileTab !== "evidence" ? "hidden lg:block" : "flex flex-1 flex-col"}`}>
                      <EvidenceDrawer
                        trace={lastPayload?.quality?.evidence_trace_summary as EvidenceTrace | string | null | undefined}
                        allCitations={allCitations}
                      />
                    </div>
                  )}
                </div>

                {reportModal && (
                  <ReportModal
                    mode={reportModal.mode}
                    suburbs={reportModal.suburbs}
                    onClose={() => setReportModal(null)}
                    payload={reportModal.mode === "single" && lastPayload ? lastPayload : undefined}
                    payloads={suburbPayloads}
                  />
                )}
              </motion.section>
            )}
          </AnimatePresence>
        </main>
      </LayoutGroup>
    </CitationHoverProvider>
  );
}
