"use client";

export function TypingDots() {
  return (
    <div className="flex w-fit items-center gap-1 rounded-[4px_16px_16px_16px] border border-slateBorder bg-slateSurface px-4 py-3">
      <span className="h-1.5 w-1.5 animate-typing-dot rounded-full bg-slateMuted" />
      <span className="h-1.5 w-1.5 animate-typing-dot animation-delay-200 rounded-full bg-slateMuted" />
      <span className="h-1.5 w-1.5 animate-typing-dot animation-delay-400 rounded-full bg-slateMuted" />
    </div>
  );
}
