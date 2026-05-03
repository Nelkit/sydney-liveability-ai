type Props = {
  title: string;
  hint?: string;
  children: React.ReactNode;
};

export function SectionCard({ title, hint, children }: Props) {
  return (
    <div className="rounded-[10px] border border-border bg-bg p-[18px]">
      <div className="mb-3 flex items-baseline justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted">
          {title}
        </span>
        {hint && (
          <span className="font-mono text-[10px] text-fg-muted">{hint}</span>
        )}
      </div>
      {children}
    </div>
  );
}
