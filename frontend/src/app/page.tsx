"use client";

import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { Coffee, Flame, Minus, Shield, Sparkles, ThumbsUp, TrainFront, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { AssistantSidebar } from "../components/liveability/AssistantSidebar";
import { importanceOptions, quickChips, suburbs, weightPrompts } from "../components/liveability/data";
import { OnboardingPanel } from "../components/liveability/OnboardingPanel";
import { SharedBrand } from "../components/liveability/SharedBrand";
import { ChatMessage, ImportanceLevelKey, Weights } from "../components/liveability/types";
import { getResponse, scoreSuburb } from "../components/liveability/utils";

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

const initialLevels: Partial<Record<keyof Weights, ImportanceLevelKey>> = {};
const PREFERENCES_STORAGE_KEY = "sydney-liveability-preferences-v1";

type StoredPreferences = {
  weights: Weights;
  selectedLevels: Partial<Record<keyof Weights, ImportanceLevelKey>>;
  profileReady: boolean;
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

  const popoverRef = useRef<HTMLDivElement | null>(null);

  const rankedSuburbs = useMemo(() => {
    return suburbs
      .map((suburb) => ({ ...suburb, computedScore: scoreSuburb(suburb, weights) }))
      .sort((a, b) => b.computedScore - a.computedScore);
  }, [weights]);

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
  }, [isHydrated, profileReady, weights, selectedLevels]);

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
    const suburb = suburbs.find((item) => item.name === name);
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

  function sendChat(text?: string) {
    const value = (text ?? chatInput).trim();
    if (!value) return;

    setChatMessages((prev) => [...prev, { role: "user", html: value }]);
    setChatInput("");
    setChatTyping(true);

    const response = getResponse(value);
    setTimeout(() => {
      setChatTyping(false);
      setChatMessages((prev) => [...prev, { role: "ai", html: response.text, source: response.source }]);
    }, 780);
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
                  suburbs={suburbs}
                  ranked={rankedSuburbs}
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
