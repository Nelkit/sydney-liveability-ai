type BarProps = {
  value: number;
  max?: number;
  color?: string;
  height?: number;
  bg?: string;
};

export function Bar({
  value,
  max = 100,
  color = "oklch(0.55 0.18 285)",
  height = 6,
  bg = "oklch(0.92 0.005 250)",
}: BarProps) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      className="relative overflow-hidden"
      style={{ height, background: bg, borderRadius: height / 2 }}
    >
      <div
        className="h-full"
        style={{ width: `${w}%`, background: color, borderRadius: height / 2 }}
      />
    </div>
  );
}

type DivergingBarProps = {
  left: number;
  right: number;
  max?: number;
};

export function DivergingBar({ left, right, max = 100 }: DivergingBarProps) {
  const lw = (left / max) * 50;
  const rw = (right / max) * 50;
  return (
    <div className="relative flex h-2 items-center">
      <div className="flex flex-1 justify-end pr-px">
        <div
          className="h-2"
          style={{
            width: `${lw}%`,
            borderRadius: "4px 0 0 4px",
            background: "oklch(0.55 0.18 25)",
          }}
        />
      </div>
      <div className="h-3.5 w-px bg-fg" />
      <div className="flex-1 pl-px">
        <div
          className="h-2"
          style={{
            width: `${rw}%`,
            borderRadius: "0 4px 4px 0",
            background: "oklch(0.55 0.18 285)",
          }}
        />
      </div>
    </div>
  );
}
