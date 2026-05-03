"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, CircleDollarSign, Coffee, MapPin, Shield, TrainFront } from "lucide-react";
import { ImportanceSlider } from "./ImportanceSlider";
import { SharedBrand } from "./SharedBrand";
import { TypingDots } from "./TypingDots";
import { ChatMessage, ImportanceLevelKey, Weights } from "./types";

type OnboardingPanelProps = {
  messages: ChatMessage[];
  typing: boolean;
  profileReady: boolean;
  onSelectOnboardingChoice: (choiceKey: ImportanceLevelKey) => void;
  weights: Weights;
  selectedLevels: Partial<Record<keyof Weights, ImportanceLevelKey>>;
  onWeightLevelChange: (key: keyof Weights, choiceKey: ImportanceLevelKey) => void;
  onContinue: () => void;
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
  onContinue
}: OnboardingPanelProps) {
  const conversationRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, typing, profileReady]);

  const isConversationStarted = messages.length > 0;
  const previewPrompts = [
    { text: "Show top suburbs near trains", icon: TrainFront, tint: "bg-bg-elev text-fg" },
    { text: "Compare safety in Newtown vs Glebe", icon: Shield, tint: "bg-bg-elev text-fg" },
    { text: "Best lifestyle picks under budget", icon: Coffee, tint: "bg-bg-elev text-fg" }
  ];

  const totalQuestions = weightMeta.length;
  const answeredQuestions = weightMeta.filter(({ key }) => Boolean(selectedLevels[key])).length;
  const progressValue = Math.round((answeredQuestions / totalQuestions) * 100);

  return (
    <motion.section
      initial={{ opacity: 0, y: 10, scale: 0.995 }}
      animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } }}
      exit={{ opacity: 0, y: -12, scale: 1.008, transition: { duration: 0.36, ease: [0.4, 0, 1, 1] } }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[radial-gradient(circle_at_30%_18%,rgba(254,215,170,0.22),transparent_28%),linear-gradient(180deg,#eff2f8,#e9edf6)]"
    >
      <div className="flex h-full w-full max-w-[860px] flex-col px-5 sm:px-7">
        <motion.div layoutId="top-shell" className="flex items-center justify-between pt-7">
          <SharedBrand />
          <div className="rounded-full border border-border bg-bg px-2.5 py-1 text-[11px] font-medium text-fg-muted shadow-float backdrop-blur">
            UTS Group 3
          </div>
        </motion.div>

        {!isConversationStarted ? (
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0, transition: { delay: 0.1, duration: 0.5 } }}
              className="w-full max-w-[680px]"
            >
              <h1 className="text-[42px] font-extrabold tracking-tight text-fg sm:text-[56px]">
                Hi there,
                <span className="bg-gradient-to-r from-slate-500 via-indigo-500 to-pink-500 bg-clip-text text-transparent"> let&apos;s find your best suburb</span>
              </h1>
              <p className="mx-auto mt-4 max-w-[560px] text-[15px] text-fg-muted sm:text-base">
                Ask anything about transport, safety, affordability, lifestyle and CBD proximity. I will build your profile in chat and then open the live map.
              </p>

              <div className="mx-auto mt-10 grid w-full max-w-[640px] gap-2.5 sm:grid-cols-3">
                {previewPrompts.map((prompt) => {
                  const PromptIcon = prompt.icon;
                  return (
                  <button
                    key={prompt.text}
                    type="button"
                    onClick={onContinue}
                    className="rounded-2xl border border-border bg-bg px-4 py-3 text-left text-[12px] font-semibold text-fg-muted shadow-float transition hover:-translate-y-[1px] hover:bg-bg-elev"
                  >
                    <span className={`mb-2 inline-flex h-7 w-7 items-center justify-center rounded-full ${prompt.tint}`}>
                      <PromptIcon size={14} />
                    </span>
                    <span className="block">{prompt.text}</span>
                  </button>
                  );
                })}
              </div>

              <motion.button
                type="button"
                onClick={onContinue}
                className="mt-8 inline-grid h-11 appearance-none place-items-center rounded-full border border-border bg-fg px-7 py-0 text-sm font-semibold text-bg shadow-floatLg transition hover:brightness-105"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0, transition: { delay: 0.25, duration: 0.4 } }}
              >
                <span className="block leading-none text-bg">
                  Start Conversation
                </span>
              </motion.button>
            </motion.div>
          </div>
        ) : (
          <div
            ref={conversationRef}
            className="scrollbar-none mx-auto flex w-full max-w-[760px] flex-1 flex-col gap-3 overflow-y-auto overflow-x-visible px-10 py-6"
          >
            {!profileReady ? (
              <div className="animate-fade-up w-full max-w-[92%] self-start rounded-2xl border border-border bg-bg p-3 shadow-float backdrop-blur">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-muted">Profile progress</p>
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
                    className="mt-4 grid h-11 w-full appearance-none place-items-center rounded-full border border-border bg-fg px-3 py-0 text-sm font-semibold text-bg transition hover:brightness-105"
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
    </motion.section>
  );
}
