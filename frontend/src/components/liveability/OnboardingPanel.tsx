"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, CircleDollarSign, Coffee, Flame, Minus, Shield, Sparkles, ThumbsUp, TrainFront, X } from "lucide-react";
import { importanceOptions } from "./data";
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
  { key: "transport", label: "Transport", icon: TrainFront, bg: "bg-blue-50" },
  { key: "safety", label: "Safety", icon: Shield, bg: "bg-green-50" },
  { key: "lifestyle", label: "Lifestyle", icon: Coffee, bg: "bg-fuchsia-50" },
  { key: "afford", label: "Affordability", icon: CircleDollarSign, bg: "bg-amber-50" }
] as const;

export function OnboardingPanel({
  messages,
  typing,
  profileReady,
  onSelectOnboardingChoice,
  weights,
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
    { text: "Show top suburbs near trains", icon: TrainFront, tint: "bg-blue-100 text-blue-700" },
    { text: "Compare safety in Newtown vs Glebe", icon: Shield, tint: "bg-emerald-100 text-emerald-700" },
    { text: "Best lifestyle picks under budget", icon: Coffee, tint: "bg-rose-100 text-rose-700" }
  ];

  const totalQuestions = weightMeta.length;
  const answeredQuestions = weightMeta.filter(({ key }) => Boolean(selectedLevels[key])).length;
  const progressValue = Math.round((answeredQuestions / totalQuestions) * 100);

  function getChoiceVisual(label: string) {
    const normalized = label.toLowerCase();
    if (normalized.includes("not very")) {
      return {
        icon: Minus,
        active: "border-slate-300 bg-slate-100 text-slate-700",
        idle: "border-slate-200 bg-white text-slate-500 hover:border-slate-400"
      };
    }
    if (normalized.includes("very")) {
      return {
        icon: Flame,
        active: "border-rose-300 bg-rose-50 text-rose-700",
        idle: "border-rose-100 bg-white text-rose-500 hover:border-rose-300"
      };
    }
    if (normalized.includes("important")) {
      return {
        icon: ThumbsUp,
        active: "border-amber-300 bg-amber-50 text-amber-700",
        idle: "border-amber-100 bg-white text-amber-600 hover:border-amber-300"
      };
    }
    if (normalized.includes("neutral")) {
      return {
        icon: Sparkles,
        active: "border-sky-300 bg-sky-50 text-sky-700",
        idle: "border-sky-100 bg-white text-sky-600 hover:border-sky-300"
      };
    }
    return {
      icon: X,
      active: "border-violet-300 bg-violet-50 text-violet-700",
      idle: "border-violet-100 bg-white text-violet-500 hover:border-violet-300"
    };
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 10, scale: 0.995 }}
      animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } }}
      exit={{ opacity: 0, y: -12, scale: 1.008, transition: { duration: 0.36, ease: [0.4, 0, 1, 1] } }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[radial-gradient(circle_at_45%_38%,rgba(252,214,173,0.25),transparent_26%),radial-gradient(circle_at_56%_56%,rgba(244,114,182,0.11),transparent_24%),linear-gradient(180deg,#f7f7fa,#f2f1f6)]"
    >
      <div className="flex h-full w-full max-w-[860px] flex-col px-5 sm:px-7">
        <motion.div layoutId="top-shell" className="flex items-center justify-between pt-7">
          <SharedBrand />
          <div className="rounded-full border border-white/75 bg-white/70 px-2.5 py-1 text-[11px] font-medium text-slate-600 shadow-[0_8px_24px_rgba(15,23,42,0.06)] backdrop-blur">
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
              <h1 className="text-[42px] font-extrabold tracking-tight text-slate-800 sm:text-[56px]">
                Hi there,
                <span className="bg-gradient-to-r from-slate-500 via-indigo-500 to-pink-500 bg-clip-text text-transparent"> let's find your best suburb</span>
              </h1>
              <p className="mx-auto mt-4 max-w-[560px] text-[15px] text-slate-500 sm:text-base">
                Ask anything about transport, safety, affordability and lifestyle. I will build your profile in chat and then open the live map.
              </p>

              <div className="mx-auto mt-10 grid w-full max-w-[640px] gap-2.5 sm:grid-cols-3">
                {previewPrompts.map((prompt) => {
                  const PromptIcon = prompt.icon;
                  return (
                  <button
                    key={prompt.text}
                    type="button"
                    onClick={onContinue}
                    className="rounded-2xl border border-white/70 bg-white/78 px-4 py-3 text-left text-[12px] font-semibold text-slate-600 shadow-[0_8px_24px_rgba(15,23,42,0.05)] transition hover:-translate-y-[1px] hover:border-slate-300"
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
                className="mt-8 inline-flex items-center rounded-full bg-gradient-to-r from-slate-900 to-slate-700 px-7 py-3 text-sm font-semibold text-white shadow-[0_10px_28px_rgba(15,23,42,0.25)] transition hover:opacity-95"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0, transition: { delay: 0.25, duration: 0.4 } }}
              >
                Start Conversation
              </motion.button>
            </motion.div>
          </div>
        ) : (
          <div
            ref={conversationRef}
            className="scrollbar-none mx-auto flex w-full max-w-[760px] flex-1 flex-col gap-3 overflow-y-auto overflow-x-visible px-10 py-6"
          >
            {!profileReady ? (
              <div className="animate-fade-up w-full max-w-[92%] self-start rounded-2xl border border-white/75 bg-white/82 p-3 shadow-[0_8px_20px_rgba(15,23,42,0.07)] backdrop-blur">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">Profile progress</p>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-700">
                    {answeredQuestions}/{totalQuestions}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
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
                      ? "rounded-[6px_16px_16px_16px] border border-white/80 bg-white/85 text-slate-700 shadow-[0_10px_28px_rgba(15,23,42,0.07)] backdrop-blur"
                      : "rounded-[16px_6px_16px_16px] bg-gradient-to-r from-slate-900 to-slate-700 text-white shadow-[0_10px_20px_rgba(15,23,42,0.25)]"
                  }`}
                  dangerouslySetInnerHTML={{ __html: message.html }}
                />
              </div>
            ))}

            {typing ? <TypingDots /> : null}

            {!profileReady && !typing ? (
              <div className="animate-fade-up w-full max-w-[92%] self-start rounded-2xl border border-white/75 bg-white/85 p-4 shadow-[0_10px_28px_rgba(15,23,42,0.08)] backdrop-blur">
                <p className="mb-2 text-xs font-semibold text-slate-500">Choose one option:</p>
                <div className="flex flex-wrap gap-2">
                  {importanceOptions.map((option) => {
                    const visual = getChoiceVisual(option.label);
                    const ChoiceIcon = visual.icon;
                    return (
                      <button
                        key={option.key}
                        type="button"
                        onClick={() => onSelectOnboardingChoice(option.key)}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold leading-none transition ${visual.idle}`}
                      >
                        <ChoiceIcon size={12} />
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {profileReady ? (
              <motion.div
                layoutId="profile-card"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-white/75 bg-white/85 p-4 shadow-[0_10px_28px_rgba(15,23,42,0.08)] backdrop-blur"
              >
                <div className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.08em] text-slate-500">
                  <CheckCircle2 size={14} className="text-emerald-500" />
                  Weighting profile ready
                </div>
                <div className="space-y-3">
                  {weightMeta.map(({ key, label, icon: Icon, bg }) => (
                    <div key={key} className="flex items-center gap-2.5">
                      <div className={`flex h-7 w-7 items-center justify-center rounded-lg text-slate-800 ${bg}`}>
                        <Icon size={14} />
                      </div>
                      <div className="w-24 text-sm font-medium text-slate-800">{label}</div>
                      <div className="flex flex-1 flex-wrap gap-1.5">
                        {importanceOptions.map((option) => {
                          const visual = getChoiceVisual(option.label);
                          const ChoiceIcon = visual.icon;
                          const active = selectedLevels[key] === option.key;
                          return (
                            <button
                              key={option.key}
                              type="button"
                              onClick={() => onWeightLevelChange(key, option.key)}
                              className={`inline-flex items-center rounded-full border px-2.5 py-1.5 text-[11px] font-medium leading-none transition ${
                                active
                                  ? `${visual.active} font-semibold`
                                  : `${visual.idle}`
                              }`}
                            >
                              <span className="inline-flex items-center gap-1 leading-none">
                                <ChoiceIcon size={11} />
                                {option.label}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                        <div className="w-10 text-right text-sm font-bold text-slate-700">{weights[key]}</div>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={onContinue}
                    className="mt-4 flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-slate-900 to-slate-700 px-3 py-3 text-sm font-semibold text-white transition hover:opacity-95"
                >
                  Continue to the main map
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
