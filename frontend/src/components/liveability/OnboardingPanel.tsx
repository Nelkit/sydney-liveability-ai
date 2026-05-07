"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowLeft, CheckCircle2, CircleDollarSign, Coffee, MapPin, Shield, TrainFront } from "lucide-react";
import { ImportanceSlider } from "./ImportanceSlider";
import { SharedBrand } from "./SharedBrand";
import { TypingDots } from "./TypingDots";
import { ChatMessage, ImportanceLevelKey, Weights } from "./types";
import { SourceBadge } from "@/components/ui/SourceBadge";

type OnboardingPanelProps = {
  messages: ChatMessage[];
  typing: boolean;
  profileReady: boolean;
  onSelectOnboardingChoice: (choiceKey: ImportanceLevelKey) => void;
  weights: Weights;
  selectedLevels: Partial<Record<keyof Weights, ImportanceLevelKey>>;
  onWeightLevelChange: (key: keyof Weights, choiceKey: ImportanceLevelKey) => void;
  onContinue: () => void;
  onBack: () => void;
};

const weightMeta = [
  { key: "transport", label: "Transport", icon: TrainFront, tint: "bg-bg-elev" },
  { key: "safety", label: "Safety", icon: Shield, tint: "bg-bg-elev" },
  { key: "lifestyle", label: "Lifestyle", icon: Coffee, tint: "bg-bg-elev" },
  { key: "afford", label: "Affordability", icon: CircleDollarSign, tint: "bg-bg-elev" },
  { key: "proximity", label: "CBD Proximity", icon: MapPin, tint: "bg-bg-elev" }
] as const;

export function OnboardingPanel({
  messages,
  typing,
  profileReady,
  onSelectOnboardingChoice,
  selectedLevels,
  onWeightLevelChange,
  onContinue,
  onBack,
}: OnboardingPanelProps) {
  const conversationRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, typing, profileReady]);

  const isConversationStarted = messages.length > 0;

  const totalQuestions = weightMeta.length;
  const answeredQuestions = weightMeta.filter(({ key }) => Boolean(selectedLevels[key])).length;
  const progressValue = Math.round((answeredQuestions / totalQuestions) * 100);

  return (
    <motion.section
      initial={{ opacity: 0, y: 10, scale: 0.995 }}
      animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } }}
      exit={{ opacity: 0, y: -12, scale: 1.008, transition: { duration: 0.36, ease: [0.4, 0, 1, 1] } }}
      className="fixed inset-0 z-50 overflow-y-auto bg-[radial-gradient(circle_at_30%_18%,rgba(254,215,170,0.22),transparent_28%),linear-gradient(180deg,#eff2f8,#e9edf6)]"
    >
      <div className="mx-auto flex w-full max-w-[860px] flex-col px-5 sm:px-7">
        <motion.div layoutId="top-shell" className="flex items-center justify-between pt-7">
          <SharedBrand />
          <div className="rounded-full border border-border bg-bg px-2.5 py-1 text-[11px] font-medium text-fg-muted shadow-float backdrop-blur">
            UTS Group 3
          </div>
        </motion.div>

        {!isConversationStarted ? (
          <>
            {/* Hero — fills the viewport, CTA stays visible above the fold */}
            <div className="flex min-h-[calc(100vh-72px)] flex-col items-center justify-center text-center">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0, transition: { delay: 0.1, duration: 0.5 } }}
                className="flex w-full max-w-[680px] flex-col items-center"
              >
                {/* Course badge */}
                <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-bg px-3.5 py-1.5 shadow-float">
                  <span className="size-1.5 rounded-full bg-indigo-400" />
                  <span className="font-mono text-[11px] text-fg-muted">ANLP 36118 · UTS · Autumn 2026</span>
                </div>

                <h1 className="text-[40px] font-extrabold tracking-tight text-fg sm:text-[54px]">
                  Find your suburb
                  <span className="block bg-gradient-to-r from-slate-500 via-indigo-500 to-pink-500 bg-clip-text text-transparent">
                    with AI-grounded data
                  </span>
                </h1>

                <p className="mx-auto mt-5 max-w-[520px] text-[14.5px] leading-relaxed text-fg-muted">
                  Compare Sydney suburbs using civic data, crime statistics, and real resident sentiment.
                  Tell me what matters to you — I&apos;ll build your profile and open the live map.
                </p>

                {/* Feature chips */}
                <div className="mt-7 flex flex-wrap justify-center gap-2">
                  {[
                    { icon: TrainFront, label: "Transport" },
                    { icon: Shield,     label: "Safety" },
                    { icon: Coffee,     label: "Lifestyle" },
                    { icon: CircleDollarSign, label: "Affordability" },
                    { icon: MapPin,     label: "CBD Proximity" },
                  ].map(({ icon: Icon, label }) => (
                    <span key={label} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg px-3 py-1.5 text-[12px] font-medium text-fg-muted shadow-float">
                      <Icon size={11} />
                      {label}
                    </span>
                  ))}
                </div>

                <motion.button
                  type="button"
                  onClick={onContinue}
                  className="mt-9 inline-grid h-12 appearance-none place-items-center rounded-full bg-fg px-8 py-0 text-[14px] font-semibold text-bg shadow-floatLg transition hover:brightness-110 active:scale-[0.98]"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0, transition: { delay: 0.3, duration: 0.4 } }}
                >
                  Start Conversation
                </motion.button>

                {/* Scroll cue — anchored to bottom of hero */}
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1, transition: { delay: 1.2, duration: 0.8 } }}
                  className="mt-14 flex flex-col items-center gap-1 text-fg-muted"
                >
                  <span className="font-mono text-[9.5px] uppercase tracking-[0.12em] opacity-50">about the project</span>
                  <motion.svg
                    width="28"
                    height="28"
                    viewBox="0 0 28 28"
                    fill="none"
                    animate={{ y: [0, 6, 0], opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <path d="M6 10l8 8 8-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </motion.svg>
                </motion.div>
              </motion.div>
            </div>

            {/* Below-the-fold sections */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0, transition: { delay: 0.45, duration: 0.55, ease: [0.22, 1, 0.36, 1] } }}
              className="flex flex-col gap-16 pb-24"
            >

              {/* Stat bar */}
              <div className="grid grid-cols-3 gap-4">
                {[
                  { value: "20k+", label: "Reddit posts indexed" },
                  { value: "600+", label: "Sydney suburbs scored" },
                  { value: "6",    label: "Live data sources" },
                ].map(({ value, label }) => (
                  <div key={label} className="flex flex-col items-center gap-1 rounded-2xl border border-border bg-bg px-4 py-5 shadow-float">
                    <span className="text-[32px] font-extrabold tracking-tight text-fg">{value}</span>
                    <span className="text-center text-[11.5px] text-fg-muted">{label}</span>
                  </div>
                ))}
              </div>

              {/* About */}
              <div className="flex flex-col gap-4">
                <SectionLabel>What is this?</SectionLabel>
                <p className="text-[14.5px] leading-[1.75] text-fg-muted">
                  Sydney Liveability AI is a suburb recommendation engine that combines structured government data,
                  real community sentiment from Reddit, and spatial analysis to help you decide where to live.
                  Ask in plain language — a multi-agent AI pipeline retrieves evidence, scores every suburb
                  against your personal weights, and explains its reasoning.
                </p>
              </div>

              {/* Data sources — card grid */}
              <div className="flex flex-col gap-4">
                <SectionLabel>Data sources</SectionLabel>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {[
                    { kind: "reddit" as const, title: "Reddit r/sydney", desc: "40k+ posts · MiniLM semantic search" },
                    { kind: "pdf" as const, title: "City of Sydney Community Reports", desc: "557 excerpts · 11 themes · MiniLM semantic search" },
                    { kind: "bocsar" as const, title: "BOCSAR",           desc: "Crime incidents by suburb · 2024" },
                    { kind: "arcgis" as const, title: "ArcGIS",           desc: "City of Sydney facilities & parks · 2026" },
                    { kind: "osm"    as const, title: "OpenStreetMap",    desc: "Cafes, schools, hospitals, pharmacies · 2026" },
                    { kind: "tfnsw" as const,  title: "Transport NSW",    desc: "Bus, train, light rail, bike paths · 2026" },
                  ].map(({ kind, title, desc }) => (
                    <div key={kind} className="flex flex-col gap-2.5 rounded-2xl border border-border bg-bg p-4 shadow-float">
                      <SourceBadge kind={kind} />
                      <div>
                        <div className="text-[13px] font-semibold text-fg">{title}</div>
                        <div className="mt-0.5 text-[11.5px] leading-snug text-fg-muted">{desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Dev card */}
              <div className="flex flex-col gap-4">
                <SectionLabel>Built by</SectionLabel>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-border bg-bg p-4 shadow-float">
                    <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.07em] text-fg-muted">Group 3 · ANLP 36118</div>
                    <div className="flex flex-col gap-1">
                      {[
                        "Ying-Kai Liao",
                        "Padmasri Srinivas",
                        "Nian-Ya Weng",
                        "Nelkit Chavez",
                        "Juan David Rodriguez",
                        "Luis Gerardo Robinson",
                      ].map((name) => (
                        <div key={name} className="text-[12.5px] text-fg">{name}</div>
                      ))}
                    </div>
                    <div className="mt-3 text-[11.5px] text-fg-muted">Master of Data Science and Innovation · UTS</div>
                  </div>
                  <div className="rounded-2xl border border-border bg-bg-elev p-4 shadow-float">
                    <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.07em] text-fg-muted">Stack</div>
                    <div className="flex flex-wrap gap-1.5">
                      {["Next.js", "FastAPI", "PostGIS", "ChromaDB", "CrewAI", "LLM", "LangChain", "Leaflet"].map((t) => (
                        <span key={t} className="rounded-full border border-border bg-bg px-2.5 py-0.5 font-mono text-[10.5px] text-fg">
                          {t}
                        </span>
                      ))}
                    </div>
                    <div className="mt-3 font-mono text-[10px] text-fg-muted">
                      {`v${process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0"}`}
                    </div>
                  </div>
                </div>
              </div>

              {/* Disclaimer */}
              <div className="rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50 to-orange-50 p-5">
                <div className="mb-2 flex items-center gap-2">
                  <AlertTriangle size={14} className="shrink-0 text-amber-500" />
                  <span className="text-[13px] font-semibold text-amber-900">Use with moderation</span>
                </div>
                <p className="text-[12.5px] leading-[1.7] text-amber-800">
                  This platform uses automated data analysis, statistical modelling, and AI-generated summaries.
                  Results reflect dataset availability and model outputs — they may not be 100% accurate or up to date.
                  Do not use this platform as the sole basis for major life decisions such as purchasing property
                  or signing a lease. Always verify with official sources.
                </p>
              </div>
            </motion.div>
          </>
        ) : (
          <div
            ref={conversationRef}
            className="scrollbar-none mx-auto flex w-full max-w-[760px] flex-1 flex-col gap-3 overflow-y-auto overflow-x-visible py-6"
          >
            {!profileReady ? (
              <div className="animate-fade-up w-full max-w-[92%] self-start rounded-2xl border border-border bg-bg p-3 shadow-float backdrop-blur">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={onBack}
                      className="flex items-center gap-1 rounded-full border border-border bg-bg-elev px-2.5 py-1 text-[11px] font-medium text-fg-muted transition hover:text-fg"
                    >
                      <ArrowLeft size={11} />
                      Back
                    </button>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-muted">Profile progress</p>
                  </div>
                  <span className="rounded-full bg-bg-elev px-2 py-0.5 text-[11px] font-bold text-fg">
                    {answeredQuestions}/{totalQuestions}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-bg-elev">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-blue-500 via-indigo-500 to-pink-500 transition-all"
                    style={{ width: `${progressValue}%` }}
                  />
                </div>
              </div>
            ) : null}

            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`animate-fade-up flex max-w-[90%] flex-col gap-1.5 ${
                  message.role === "ai" ? "self-start" : "self-end"
                }`}
              >
                <div
                  className={`px-4 py-3 text-sm leading-relaxed ${
                    message.role === "ai"
                      ? "rounded-[6px_16px_16px_16px] border border-border bg-bg text-fg shadow-float backdrop-blur"
                      : "rounded-[16px_6px_16px_16px] bg-fg text-bg shadow-floatLg"
                  }`}
                  dangerouslySetInnerHTML={{ __html: message.html }}
                />
              </div>
            ))}

            {typing ? <TypingDots /> : null}

            {!profileReady && !typing ? (
              <div className="animate-fade-up w-full max-w-[92%] self-start rounded-2xl border border-border bg-bg p-4 shadow-float backdrop-blur">
                <p className="mb-4 text-xs font-semibold text-fg-muted">Rate your preference (1 = low, 10 = high)</p>
                <ImportanceSlider value={undefined} onChange={onSelectOnboardingChoice} />
              </div>
            ) : null}

            {profileReady ? (
              <motion.div
                layoutId="profile-card"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-border bg-bg p-4 shadow-float backdrop-blur"
              >
                <div className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.08em] text-fg-muted">
                  <CheckCircle2 size={14} className="text-emerald-500" />
                  Weighting profile ready
                </div>
                <div className="space-y-3">
                  {weightMeta.map(({ key, label, icon: Icon, tint }) => (
                    <div key={key} className="flex items-center gap-2.5">
                      <div className={`flex h-7 w-7 items-center justify-center rounded-lg text-fg ${tint}`}>
                        <Icon size={14} />
                      </div>
                      <div className="w-20 shrink-0 text-sm font-medium text-fg">{label}</div>
                      <div className="flex flex-1 items-center gap-3">
                        <ImportanceSlider
                          value={selectedLevels[key]}
                          onChange={(k) => onWeightLevelChange(key, k)}
                        />
                        <div className="w-6 shrink-0 text-right text-sm font-bold text-fg">
                          {selectedLevels[key] ?? "–"}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={onContinue}
                    className="mt-4 grid h-11 w-full appearance-none place-items-center rounded-full bg-fg px-3 py-0 text-sm font-semibold text-bg transition hover:brightness-105"
                >
                  <span className="block leading-none text-bg">
                    Continue to the main map
                  </span>
                </button>
              </motion.div>
            ) : null}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <footer className="shrink-0 border-t border-border px-6 py-3 flex items-center justify-center gap-2 text-[11px] text-fg-muted font-mono">
        <span>© {new Date().getFullYear()} Sydney Liveability AI</span>
        <span className="text-border select-none">·</span>
        <a
          href="https://github.com/Nelkit/sydney-liveability-ai"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg px-2.5 py-1 text-fg shadow-float transition hover:border-fg hover:shadow-none"
        >
          <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor" aria-hidden="true">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
          </svg>
          GitHub
        </a>
      </footer>
    </motion.section>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-fg-muted">
      {children}
    </div>
  );
}
