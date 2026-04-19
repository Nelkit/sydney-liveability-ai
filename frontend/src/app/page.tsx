"use client";

import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { Coffee, Flame, Minus, Shield, Sparkles, ThumbsUp, TrainFront, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { AssistantSidebar } from "../components/liveability/AssistantSidebar";
import { importanceOptions, quickChips, suburbs, weightPrompts } from "../components/liveability/data";
import { OnboardingPanel } from "../components/liveability/OnboardingPanel";
import { SharedBrand } from "../components/liveability/SharedBrand";
import { ChatMessage, ImportanceLevelKey, Weights, Suburb } from "../components/liveability/types";
import { scoreSuburb } from "../components/liveability/utils";

const MapPanel = dynamic(
  () => import("../components/liveability/MapPanel").then((module) => module.MapPanel),
  { ssr: false }
);

const initialWeights: Weights = {
  transport: 0,
  safety: 0,
  lifestyle: 0,
  afford: 0
};

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const CHAT_ENDPOINT = `${API_BASE_URL}/api/chat`;
const CIVIC_ENDPOINT = `${API_BASE_URL}/api/civic`;

const initialLevels: Partial<Record<keyof Weights, ImportanceLevelKey>> = {};
const PREFERENCES_STORAGE_KEY = "sydney-liveability-preferences-v1";
const USER_WEIGHTS_STORAGE_KEY = "user_weights";

type UserWeightLabels = {
  transport?: string;
  safety?: string;
  lifestyle?: string;
  affordability?: string;
  nightlife?: string;
};

function getUserWeights() {
  const defaults = {
    transport: 0.2,
    safety: 0.2,
    lifestyle: 0.2,
    affordability: 0.2,
    nightlife: 0.2
  };

  const importanceMap: Record<string, number> = {
    "Very important": 4,
    Important: 3,
    Neutral: 2,
    "Not very important": 1,
    "Not interested": 0
  };

  try {
    const stored = window.localStorage.getItem(USER_WEIGHTS_STORAGE_KEY);
    if (!stored) return defaults;

    const prefs = JSON.parse(stored) as UserWeightLabels;
    const keys = ["transport", "safety", "lifestyle", "affordability", "nightlife"] as const;

    const raw: Record<(typeof keys)[number], number> = {
      transport: 0,
      safety: 0,
      lifestyle: 0,
      affordability: 0,
      nightlife: 0
    };

    let total = 0;
    for (const key of keys) {
      const label = prefs[key];
      const score = typeof label === "string" ? (importanceMap[label] ?? 2) : 2;
      raw[key] = score;
      total += score;
    }

    if (total === 0) return defaults;

    const weights: Record<(typeof keys)[number], number> = {
      transport: 0,
      safety: 0,
      lifestyle: 0,
      affordability: 0,
      nightlife: 0
    };
    for (const key of keys) {
      weights[key] = parseFloat((raw[key] / total).toFixed(4));
    }

    return weights;
  } catch {
    return defaults;
  }
}

function extractCenterAndPolygon(geometry: CivicGeometry | Record<string, never>): { center: [number, number]; polygon: [number, number][] } {
  // Default fallback center (Sydney CBD)
  const fallback = { center: [-33.8688, 151.2093] as [number, number], polygon: [] as [number, number][] };

  if (!geometry || !("type" in geometry) || geometry.type !== "MultiPolygon" || !Array.isArray(geometry.coordinates)) {
    return fallback;
  }

  try {
    // For MultiPolygon: [[[outer_ring], [hole1], ...], [[outer_ring], ...], ...]
    // We want the first polygon's outer ring
    const firstPolygon = geometry.coordinates[0] as unknown[][];
    if (!Array.isArray(firstPolygon) || firstPolygon.length === 0) {
      return fallback;
    }

    const outerRing = firstPolygon[0] as unknown[][];
    if (!Array.isArray(outerRing) || outerRing.length === 0) {
      return fallback;
    }

    // Convert [lng, lat] to [lat, lng] for Leaflet
    const polygonCoords = outerRing
      .filter((coord) => Array.isArray(coord) && coord.length >= 2)
      .map((coord) => [coord[1], coord[0]] as [number, number]);

    if (polygonCoords.length === 0) {
      return fallback;
    }

    // Calculate center (centroid of first polygon)
    const sumLat = polygonCoords.reduce((sum, [lat]) => sum + lat, 0);
    const sumLng = polygonCoords.reduce((sum, [, lng]) => sum + lng, 0);
    const center: [number, number] = [sumLat / polygonCoords.length, sumLng / polygonCoords.length];

    return { center, polygon: polygonCoords };
  } catch {
    return fallback;
  }
}

function convertCivicFeaturesToSuburbs(civicResponse: CivicResponse): Suburb[] {
  const colorMap: Record<string, string> = {
    newtown: "#3b82f6",
    glebe: "#10b981",
    redfern: "#f59e0b",
    "surry hills": "#8b5cf6",
    haymarket: "#ef4444"
  };

  return civicResponse.features.map((feature) => {
    const { suburb, liveability_score, safety_score, transport_score, lifestyle_score } = feature.properties;
    const { center, polygon } = extractCenterAndPolygon(feature.geometry);

    const suburbLower = suburb.toLowerCase();
    const color = colorMap[suburbLower] || "#6366f1";

    return {
      id: suburbLower.replace(/\s+/g, "-"),
      name: suburb,
      color,
      scoreBase: {
        transport: Math.round(transport_score * 100),
        safety: Math.round(safety_score * 100),
        lifestyle: Math.round(lifestyle_score * 100),
        afford: 50 // Placeholder; affordability_score not directly used in scoreSuburb
      },
      center,
      polygon
    };
  });
}

type StoredPreferences = {
  weights: Weights;
  selectedLevels: Partial<Record<keyof Weights, ImportanceLevelKey>>;
  profileReady: boolean;
};

type ChatApiSource = {
  text?: string;
  suburb?: string;
  source?: string;
};

type ChatApiResponse = {
  answer?: string;
  sources?: ChatApiSource[];
};

type CivicGeometry = {
  type: string;
  coordinates: unknown;
};

type CivicFeatureProperties = {
  suburb: string;
  sa4_area: string;
  liveability_score: number;
  safety_score: number;
  transport_score: number;
  lifestyle_score: number;
  nightlife_score: number;
};

type CivicFeature = {
  type: "Feature";
  properties: CivicFeatureProperties;
  geometry: CivicGeometry | Record<string, never>;
};

type CivicResponse = {
  type: "FeatureCollection";
  features: CivicFeature[];
};

function isValidWeights(value: unknown): value is Weights {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.transport === "number" &&
    typeof candidate.safety === "number" &&
    typeof candidate.lifestyle === "number" &&
    typeof candidate.afford === "number"
  );
}

function isValidSelectedLevels(value: unknown): value is Partial<Record<keyof Weights, ImportanceLevelKey>> {
  if (!value || typeof value !== "object") return false;
  const validKeys = new Set(importanceOptions.map((option) => option.key));
  const candidate = value as Record<string, unknown>;
  const keys: (keyof Weights)[] = ["transport", "safety", "lifestyle", "afford"];
  return keys.every((key) => candidate[key] === undefined || (typeof candidate[key] === "string" && validKeys.has(candidate[key] as ImportanceLevelKey)));
}

function getImportanceScore(choiceKey: ImportanceLevelKey) {
  return importanceOptions.find((option) => option.key === choiceKey)?.value ?? 50;
}

function getImportanceLabel(choiceKey?: ImportanceLevelKey) {
  if (!choiceKey) return "Unset";
  return importanceOptions.find((option) => option.key === choiceKey)?.label ?? "Unset";
}

function getImportanceVisual(choiceKey: ImportanceLevelKey) {
  if (choiceKey === "veryImportant") {
    return {
      icon: Flame,
      active: "border-rose-300 bg-rose-50 text-rose-700",
      idle: "border-rose-100 bg-white text-rose-500 hover:border-rose-300"
    };
  }
  if (choiceKey === "important") {
    return {
      icon: ThumbsUp,
      active: "border-amber-300 bg-amber-50 text-amber-700",
      idle: "border-amber-100 bg-white text-amber-600 hover:border-amber-300"
    };
  }
  if (choiceKey === "neutral") {
    return {
      icon: Sparkles,
      active: "border-sky-300 bg-sky-50 text-sky-700",
      idle: "border-sky-100 bg-white text-sky-600 hover:border-sky-300"
    };
  }
  if (choiceKey === "notVeryImportant") {
    return {
      icon: Minus,
      active: "border-slate-300 bg-slate-100 text-slate-700",
      idle: "border-slate-200 bg-white text-slate-500 hover:border-slate-400"
    };
  }
  return {
    icon: X,
    active: "border-violet-300 bg-violet-50 text-violet-700",
    idle: "border-violet-100 bg-white text-violet-500 hover:border-violet-300"
  };
}

export default function HomePage() {
  const [isHydrated, setIsHydrated] = useState(false);
  const [isAppOpen, setIsAppOpen] = useState(false);

  const [weights, setWeights] = useState<Weights>(initialWeights);
  const [selectedLevels, setSelectedLevels] = useState<Partial<Record<keyof Weights, ImportanceLevelKey>>>(initialLevels);
  const [profileReady, setProfileReady] = useState(false);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);

  const [onboardingMessages, setOnboardingMessages] = useState<ChatMessage[]>([]);
  const [onboardingTyping, setOnboardingTyping] = useState(false);

  const [selectedSuburbId, setSelectedSuburbId] = useState<string | null>(null);
  const [layer, setLayer] = useState("Liveability");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatTyping, setChatTyping] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [pdfLoaded, setPdfLoaded] = useState(false);
  const [civicData, setCivicData] = useState<CivicResponse | null>(null);
  const [isCivicLoading, setIsCivicLoading] = useState(true);

  const popoverRef = useRef<HTMLDivElement | null>(null);

  const rankedSuburbs = useMemo(() => {
    // Use real civic data if available.
    const suburbsToRank = civicData ? convertCivicFeaturesToSuburbs(civicData) : suburbs;

    if (civicData) {
      // Already ranked by liveability_score from civic endpoint
      return civicData.features.map((feature, index) => {
        const suburb = suburbsToRank[index];
        return { ...suburb, computedScore: Math.round(feature.properties.liveability_score * 100) };
      });
    }

    // While civic is loading we show placeholders in map/cards instead of static demo suburbs.
    if (isCivicLoading) {
      return [];
    }

    // Fall back to local scoring for static data
    return suburbsToRank
      .map((suburb) => ({ ...suburb, computedScore: scoreSuburb(suburb, weights) }))
      .sort((a, b) => b.computedScore - a.computedScore);
  }, [weights, civicData, isCivicLoading]);

  const allSuburbsForMap = useMemo(() => {
    if (isCivicLoading && !civicData) return [];
    return civicData ? convertCivicFeaturesToSuburbs(civicData) : suburbs;
  }, [civicData, isCivicLoading]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PREFERENCES_STORAGE_KEY);
      if (!raw) {
        setIsHydrated(true);
        return;
      }

      const parsed = JSON.parse(raw) as StoredPreferences;
      if (!isValidWeights(parsed.weights) || !isValidSelectedLevels(parsed.selectedLevels) || !parsed.profileReady) {
        setIsHydrated(true);
        return;
      }

      setWeights(parsed.weights);
      setSelectedLevels(parsed.selectedLevels);
      setProfileReady(true);
      setIsAppOpen(true);
    } catch {
      // Ignore malformed storage and continue with first-time onboarding.
    } finally {
      setIsHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!isHydrated || !profileReady) return;

    const payload: StoredPreferences = {
      weights,
      selectedLevels,
      profileReady: true
    };

    window.localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(payload));

    const keyToLabel = {
      transport: getImportanceLabel(selectedLevels.transport),
      safety: getImportanceLabel(selectedLevels.safety),
      lifestyle: getImportanceLabel(selectedLevels.lifestyle),
      affordability: getImportanceLabel(selectedLevels.afford),
      nightlife: "Neutral"
    };
    window.localStorage.setItem(USER_WEIGHTS_STORAGE_KEY, JSON.stringify(keyToLabel));
  }, [isHydrated, profileReady, weights, selectedLevels]);

  useEffect(() => {
    if (!isHydrated) return;

    setIsCivicLoading(true);

    const numericWeights = getUserWeights();
    const params = new URLSearchParams(
      Object.entries(numericWeights).map(([key, value]) => [key, String(value)])
    );

    void fetch(`${CIVIC_ENDPOINT}?${params.toString()}`, { method: "GET" })
      .then((response) => {
        if (!response.ok) throw new Error(`Civic API failed with status ${response.status}`);
        return response.json() as Promise<CivicResponse>;
      })
      .then((data) => {
        setCivicData(data);
      })
      .catch(() => {
        // Silently fail and continue with static data
      })
      .finally(() => {
        setIsCivicLoading(false);
      });
  }, [isHydrated, selectedLevels]);

  function startOnboardingConversation() {
    setOnboardingTyping(true);
    setTimeout(() => {
      setOnboardingTyping(false);
      setOnboardingMessages([
        {
          role: "ai",
          html: "Hi, I am your <strong>Sydney Liveability AI</strong>. Let us build your weighting profile in a conversational way."
        },
        {
          role: "ai",
          html: weightPrompts[0].prompt
        }
      ]);
    }, 400);
  }

  useEffect(() => {
    if (!isAppOpen) return;
    setChatMessages([
      {
        role: "ai",
        html: "Profile saved. You now have a real Sydney map with active demo layers. You can adjust weights anytime from the profile widget.",
        source: "13,500+ entries - BOCSAR - ArcGIS - Reddit"
      }
    ]);
  }, [isAppOpen]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (!popoverRef.current) return;
      if (popoverRef.current.contains(event.target as Node)) return;
      setProfileOpen(false);
    };

    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function updateWeight(key: keyof Weights, value: number) {
    setWeights((prev) => ({ ...prev, [key]: value }));
  }

  function applyWeightChoice(key: keyof Weights, choiceKey: ImportanceLevelKey) {
    updateWeight(key, getImportanceScore(choiceKey));
    setSelectedLevels((prev) => ({ ...prev, [key]: choiceKey }));
  }

  function handleOnboardingChoice(choiceKey: ImportanceLevelKey) {
    if (profileReady) return;

    const prompt = weightPrompts[currentQuestionIndex];
    const choiceLabel = getImportanceLabel(choiceKey);
    setOnboardingMessages((prev) => [...prev, { role: "user", html: `${prompt.label}: ${choiceLabel}` }]);

    applyWeightChoice(prompt.key, choiceKey);

    const nextIndex = currentQuestionIndex + 1;
    if (nextIndex < weightPrompts.length) {
      setCurrentQuestionIndex(nextIndex);
      setOnboardingTyping(true);
      setTimeout(() => {
        setOnboardingTyping(false);
        setOnboardingMessages((prev) => [
          ...prev,
          {
            role: "ai",
            html: `Perfect. ${weightPrompts[nextIndex].prompt}`
          }
        ]);
      }, 420);
      return;
    }

    setProfileReady(true);
    setOnboardingMessages((prev) => [
      ...prev,
      {
        role: "ai",
        html: "Excellent, we have captured your profile. You can fine-tune each category using the same choice levels and then continue to the map."
      }
    ]);
  }

  function openMainApp() {
    if (!profileReady) return;
    setIsAppOpen(true);
  }

  function onSelectSuburb(name: string) {
    const suburb = allSuburbsForMap.find((item) => item.name === name);
    if (!suburb) return;
    setSelectedSuburbId(suburb.id);

    const scored = scoreSuburb(suburb, weights);
    setChatMessages((prev) => [
      ...prev,
      {
        role: "ai",
        html: `You selected <strong>${suburb.name}</strong>. Current score: <strong style='color:${suburb.color}'>${scored}/100</strong>.`,
        source: "BOCSAR - City of Sydney ArcGIS - Community Insights 2024 - Reddit"
      }
    ]);
  }

  async function sendChat(text?: string) {
    const value = (text ?? chatInput).trim();
    if (!value) return;

    setChatMessages((prev) => [...prev, { role: "user", html: value }]);
    setChatInput("");
    setChatTyping(true);

    try {
      const apiResponse = await fetch(CHAT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: value,
          weights: getUserWeights()
        })
      });

      if (!apiResponse.ok) {
        throw new Error(`Chat API request failed with status ${apiResponse.status}`);
      }

      const payload = (await apiResponse.json()) as ChatApiResponse;
      const answer = (payload.answer ?? "I could not process that question right now.").trim();
      const source = Array.isArray(payload.sources) && payload.sources.length > 0
        ? payload.sources
            .map((item) => [item.source, item.suburb].filter(Boolean).join(" - "))
            .filter(Boolean)
            .join(" | ")
        : "Sydney Liveability API";

      setChatTyping(false);
      setChatMessages((prev) => [...prev, { role: "ai", html: answer, source }]);
    } catch {
      setChatTyping(false);
      setChatMessages((prev) => [
        ...prev,
        {
          role: "ai",
          html: "I could not process that question right now. Please try again.",
          source: "Sydney Liveability API"
        }
      ]);
    }
  }

  function togglePdf() {
    setPdfLoaded((prev) => {
      const next = !prev;
      if (next) {
        setChatMessages((old) => [
          ...old,
          {
            role: "ai",
            html: "PDF loaded. <strong>45 King St, Newtown</strong> is a 12-minute walk from Newtown Station and in a low crime-density zone.",
            source: "Address-level RAG - City of Sydney ArcGIS - BOCSAR"
          }
        ]);
      }
      return next;
    });
  }

  function resetPreferences() {
    window.localStorage.removeItem(PREFERENCES_STORAGE_KEY);
    window.localStorage.removeItem(USER_WEIGHTS_STORAGE_KEY);
    setWeights(initialWeights);
    setSelectedLevels(initialLevels);
    setProfileReady(false);
    setCurrentQuestionIndex(0);
    setOnboardingMessages([]);
    setOnboardingTyping(false);
    setSelectedSuburbId(null);
    setChatMessages([]);
    setChatTyping(false);
    setChatInput("");
    setProfileOpen(false);
    setPdfLoaded(false);
    setIsAppOpen(false);
  }

  if (!isHydrated) {
    return <main className="h-screen" />;
  }

  return (
    <LayoutGroup>
      <main className="h-screen overflow-hidden font-['Manrope',sans-serif] text-slateText">
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
              onContinue={profileReady ? openMainApp : startOnboardingConversation}
            />
          ) : (
            <motion.section
              key="main-app"
              initial={{ opacity: 0, scale: 0.992, y: 14 }}
              animate={{
                opacity: 1,
                scale: 1,
                y: 0,
                transition: { duration: 0.46, ease: [0.22, 1, 0.36, 1], delay: 0.02 }
              }}
              exit={{ opacity: 0, scale: 1.006, y: -8, transition: { duration: 0.26, ease: [0.4, 0, 1, 1] } }}
              className="grid h-screen grid-rows-[56px_1fr] bg-[radial-gradient(circle_at_48%_22%,rgba(251,207,232,0.2),transparent_30%),linear-gradient(180deg,#f6f7fa,#f0f2f7)]"
            >
              <header className="relative z-[700] col-span-full flex items-center gap-3 border-b border-slate-200/80 bg-white/70 px-4 backdrop-blur lg:px-5">
                <motion.div layoutId="top-shell">
                  <SharedBrand compact />
                </motion.div>

                <div className="h-5 w-px bg-slate-200" />

                <div ref={popoverRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setProfileOpen((prev) => !prev)}
                    className="flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 shadow-[0_6px_16px_rgba(15,23,42,0.06)]"
                  >
                    <span className="text-[10px] font-bold tracking-[0.04em] text-slate-700">MY PROFILE</span>
                    <span className="inline-flex h-6 items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 text-[10px] font-semibold leading-none text-slate-700">
                      <TrainFront size={10} /> {getImportanceLabel(selectedLevels.transport)}
                    </span>
                    <span className="inline-flex h-6 items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 text-[10px] font-semibold leading-none text-slate-700">
                      <Shield size={10} /> {getImportanceLabel(selectedLevels.safety)}
                    </span>
                    <span className="hidden h-6 items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 text-[10px] font-semibold leading-none text-slate-700 sm:inline-flex">
                      <Coffee size={10} /> {getImportanceLabel(selectedLevels.lifestyle)}
                    </span>
                  </button>

                  {profileOpen ? (
                    <motion.div
                      layoutId="profile-card"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="absolute left-0 top-[calc(100%+8px)] z-[900] w-max max-w-[94vw] rounded-xl2 border border-slate-200 bg-white/95 p-4 shadow-cardLg backdrop-blur"
                    >
                      <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.07em] text-slate-500">Adjust weighting profile</p>
                      <div className="min-w-[620px] max-w-[760px] space-y-0">
                        {([
                          ["transport", "Transport"],
                          ["safety", "Safety"],
                          ["lifestyle", "Lifestyle"],
                          ["afford", "Affordability"]
                        ] as [keyof Weights, string][]).map(([key, label], index, allItems) => (
                          <div
                            key={key}
                            className={`${index < allItems.length - 1 ? "mb-4 border-b border-slate-200/90 pb-4" : ""}`}
                          >
                            <span className="mb-2 block text-sm font-semibold text-slate-700">{label}</span>
                            <div className="scrollbar-none flex gap-1.5 overflow-x-auto pb-1">
                              {importanceOptions.map((option) => {
                                const active = selectedLevels[key] === option.key;
                                const visual = getImportanceVisual(option.key);
                                const OptionIcon = visual.icon;
                                return (
                                  <button
                                    key={option.key}
                                    type="button"
                                    onClick={() => applyWeightChoice(key, option.key)}
                                    className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-1.5 text-[11px] font-medium leading-none transition ${
                                      active
                                        ? `${visual.active} font-semibold`
                                        : `${visual.idle}`
                                    }`}
                                  >
                                    <span className="inline-flex items-center gap-1 leading-none">
                                      <OptionIcon size={11} />
                                      {option.label}
                                    </span>
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>

                      <button
                        type="button"
                        onClick={resetPreferences}
                        className="mt-4 w-full rounded-full border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-500 hover:text-slate-900"
                      >
                        Reset preferences
                      </button>
                    </motion.div>
                  ) : null}
                </div>
              </header>

              <div className="relative h-full min-h-0">
                <MapPanel
                  suburbs={allSuburbsForMap}
                  ranked={rankedSuburbs}
                  isLoading={isCivicLoading && !civicData}
                  selectedSuburbId={selectedSuburbId}
                  onSelectSuburb={onSelectSuburb}
                  layer={layer}
                  onLayerChange={setLayer}
                  weights={weights}
                />

                <div className="pointer-events-none absolute inset-y-3 left-3 z-[650] w-[330px] max-w-[calc(100%-24px)] sm:w-[350px]">
                  <div className="pointer-events-auto h-full">
                    <AssistantSidebar
                      messages={chatMessages}
                      typing={chatTyping}
                      input={chatInput}
                      onInputChange={setChatInput}
                      onSend={() => sendChat()}
                      onChipSend={sendChat}
                      chips={quickChips}
                      pdfLoaded={pdfLoaded}
                      onTogglePdf={togglePdf}
                    />
                  </div>
                </div>
              </div>
            </motion.section>
          )}
        </AnimatePresence>
      </main>
    </LayoutGroup>
  );
}
