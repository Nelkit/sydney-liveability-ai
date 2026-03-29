"use client";

import { FileText, SendHorizontal, Sparkles, X } from "lucide-react";
import Image from "next/image";
import { ChatMessage } from "./types";
import { TypingDots } from "./TypingDots";

type AssistantSidebarProps = {
  messages: ChatMessage[];
  typing: boolean;
  input: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onChipSend: (text: string) => void;
  chips: string[];
  pdfLoaded: boolean;
  onTogglePdf: () => void;
};

export function AssistantSidebar({
  messages,
  typing,
  input,
  onInputChange,
  onSend,
  onChipSend,
  chips,
  pdfLoaded,
  onTogglePdf
}: AssistantSidebarProps) {
  return (
    <aside className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white/94 shadow-[0_20px_45px_rgba(15,23,42,0.16)] backdrop-blur">
      <div className="shrink-0 bg-white flex items-center gap-2 border-b border-slate-200/80 px-3 py-2.5">
        <div className="relative h-6 w-6 overflow-hidden rounded-full border border-slate-200 bg-white">
          <Image
            src="/img/logo.webp"
            alt="Sydney Liveability AI logo"
            fill
            sizes="24px"
            className="object-cover"
            priority
          />
        </div>
        <div className="min-w-0">
          <p className="truncate text-[11px] font-semibold text-slate-800">Liveability Assistant</p>
        </div>
        <div className="ml-auto flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-600">
          <Sparkles size={10} />
          Live
        </div>
        <button type="button" className="rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600" aria-label="Close panel">
          <X size={13} />
        </button>
      </div>

      <div className="scrollbar-none min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-2.5">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`animate-fade-up ${message.role === "ai" ? "mr-5" : "ml-5"}`}>
            <div
              className={`rounded-[10px] px-2.5 py-2 text-[12px] leading-relaxed ${
                message.role === "ai"
                  ? "rounded-tl-[4px] border border-slate-200 bg-slate-50 text-slate-700"
                  : "rounded-tr-[4px] bg-gradient-to-r from-slate-900 to-slate-700 text-white shadow-[0_8px_16px_rgba(15,23,42,0.24)]"
              }`}
              dangerouslySetInnerHTML={{ __html: message.html }}
            />
            {message.source ? <p className="mt-1 border-t border-slate-200 pt-1 text-[10px] text-slate-500">{message.source}</p> : null}
          </div>
        ))}

        {typing ? (
          <div className="mr-5">
            <TypingDots />
          </div>
        ) : null}
      </div>

      <button
        type="button"
        onClick={onTogglePdf}
        className={`mx-3 mb-2 shrink-0 flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-[10px] transition ${
          pdfLoaded
            ? "border-emerald-300 bg-emerald-50 text-emerald-600"
            : "border-dashed border-slate-300 text-slate-500 hover:border-slate-500 hover:text-slate-700"
        }`}
      >
        <FileText size={14} />
        <span>{pdfLoaded ? "rental_listing_newtown.pdf loaded" : "Upload rental PDF for address-level advice"}</span>
      </button>

      <div className="shrink-0 flex flex-wrap gap-1.5 px-3 pb-2">
        {chips.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => onChipSend(chip)}
            className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.04em] text-slate-500 transition hover:border-slate-500 hover:text-slate-700"
          >
            {chip}
          </button>
        ))}
      </div>

      <div className="shrink-0 flex items-end gap-2 border-t border-slate-200/80 bg-slate-50/80 px-3 py-2.5">
        <textarea
          value={input}
          rows={1}
          placeholder='Try: "safe and near transport"'
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
          className="max-h-24 min-h-10 flex-1 resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
        />
        <button
          type="button"
          onClick={onSend}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-r from-slate-900 to-slate-700 text-white transition hover:opacity-95"
        >
          <SendHorizontal size={14} />
        </button>
      </div>
    </aside>
  );
}
