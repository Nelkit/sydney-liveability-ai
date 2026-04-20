"use client";

import { ArrowLeft } from "lucide-react";
import { RedditNLPAnalysis } from "../liveability/RedditNLPAnalysis";

interface DetailedReportModalProps {
  isOpen: boolean;
  messageHtml?: string | null;
  suburb: string | null;
  title?: string;
  subtitle?: string;
  onClose: () => void;
}

export function DetailedReportModal({
  isOpen,
  messageHtml,
  suburb,
  title = "Detailed Report",
  subtitle = "Full assistant response and suburb-level NLP deep analysis",
  onClose,
}: DetailedReportModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center bg-black/45 p-6 pt-8 backdrop-blur-sm sm:p-8 sm:pt-10"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Detailed report"
    >
      <div
        className="relative flex h-[calc(100vh-4rem)] w-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200/80 bg-white/95 px-5 py-4 backdrop-blur">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
            aria-label="Go back"
          >
            <ArrowLeft size={16} />
            Go back
          </button>
          <div className="flex-1 pl-4">
            <h2 className="text-left text-lg font-bold text-slate-900">{title}</h2>
            <p className="mt-1 text-left text-[12px] text-slate-600">{subtitle}</p>
          </div>
          <div className="w-[92px]" />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          {messageHtml ? (
            <section className="rounded-xl2 border border-slate-200 bg-white p-5 shadow-card">
              <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500">
                Assistant response
              </h3>
              <div
                className="mt-3 whitespace-pre-wrap text-[14px] leading-relaxed text-slate-700"
                dangerouslySetInnerHTML={{ __html: messageHtml }}
              />
            </section>
          ) : null}

          <RedditNLPAnalysis suburb={suburb} />
        </div>
      </div>
    </div>
  );
}