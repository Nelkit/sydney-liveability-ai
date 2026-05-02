import type { RedditHighlight } from "@/types/api";

const SENT_COLOR: Record<string, string> = {
  pos: "oklch(0.55 0.16 145)",
  neu: "oklch(0.65 0.02 250)",
  neg: "oklch(0.55 0.18 25)",
};

type Props = {
  q: RedditHighlight;
  variant?: "compact" | "full";
  accent?: string;
};

export function RedditQuote({ q, variant = "full", accent }: Props) {
  const sentColor = SENT_COLOR[q.sentiment] ?? SENT_COLOR.neu;
  const borderColor = accent ?? sentColor;

  return (
    <div
      className="flex flex-col gap-2.5 rounded-lg border border-border bg-bg-elev p-3"
      style={{ borderLeft: `3px solid ${borderColor}` }}
    >
      <div className={`leading-[1.55] text-fg ${variant === "full" ? "text-[12.5px]" : "text-[12px]"}`}>
        &ldquo;{q.q}&rdquo;
      </div>
      <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] text-fg-muted">
        <span className="rounded border border-border bg-bg px-[5px] py-px text-fg">
          {q.aspect}
        </span>
        <span style={{ color: sentColor, fontWeight: 600 }}>{q.sentiment}</span>
        <span>↑{q.up}</span>
        <span className="flex-1" />
        <a
          href={`https://reddit.com/comments/${q.id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-fg"
        >
          reddit/{q.id}
        </a>
      </div>
    </div>
  );
}
