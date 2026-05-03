import type { SourceKind } from "@/types/api";

const LABELS: Record<SourceKind, string> = {
  reddit: "Reddit",
  bocsar: "BOCSAR",
  arcgis: "ArcGIS",
  osm:    "OSM",
  tfnsw:  "TfNSW",
  pdf:    "PDF",
};

type Props = {
  kind: SourceKind;
  n?: number;
  onClick?: () => void;
};

export function SourceBadge({ kind, n, onClick }: Props) {
  const label = LABELS[kind] ?? kind;
  const content = (
    <>
      <span className="inline-flex size-[14px] items-center justify-center rounded-[3px] bg-fg text-bg text-[8px] font-bold">
        {label[0]}
      </span>
      <span>{label}</span>
      {n != null && <span className="text-fg-muted">·{n}</span>}
    </>
  );

  const className = "inline-flex items-center gap-1 rounded border border-border bg-bg-elev px-[7px] py-[2px] font-mono text-[10.5px] leading-[1.4] text-fg";

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${className} cursor-pointer`}
      >
        {content}
      </button>
    );
  }

  return (
    <span className={className}>
      {content}
    </span>
  );
}
