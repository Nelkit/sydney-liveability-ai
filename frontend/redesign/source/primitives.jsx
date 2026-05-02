// Shared primitives: chips, dots, mini map, sparkline, etc.
const { useState, useRef, useEffect, useMemo } = React;

// ---------- Router category chip ----------
function CategoryChip({ kind, active = true, size = "sm" }) {
  const map = {
    crime:      { label: "crime",      hue: 25  },
    gis:        { label: "gis",        hue: 235 },
    sentiment:  { label: "sentiment",  hue: 75  },
    comparator: { label: "comparator", hue: 285 },
    out_of_scope: { label: "out_of_scope", hue: 0, mute: true },
  };
  const c = map[kind] || { label: kind, hue: 250 };
  const bg = c.mute
    ? `oklch(0.96 0.005 ${c.hue})`
    : `oklch(0.96 0.04 ${c.hue})`;
  const fg = c.mute
    ? `oklch(0.55 0.01 ${c.hue})`
    : `oklch(0.40 0.14 ${c.hue})`;
  const bd = c.mute
    ? `oklch(0.90 0.005 ${c.hue})`
    : `oklch(0.85 0.05 ${c.hue})`;
  const dot = c.mute
    ? `oklch(0.65 0.02 ${c.hue})`
    : `oklch(0.55 0.16 ${c.hue})`;
  const padY = size === "xs" ? 2 : 3;
  const padX = size === "xs" ? 6 : 8;
  const fs = size === "xs" ? 10 : 11;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: `${padY}px ${padX}px`, borderRadius: 999,
      background: active ? bg : "transparent",
      border: `1px solid ${active ? bd : "var(--border)"}`,
      color: active ? fg : "var(--muted)",
      fontFamily: "var(--mono)", fontSize: fs, fontWeight: 500,
      letterSpacing: "0.02em", textTransform: "lowercase",
      whiteSpace: "nowrap",
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: 999,
        background: active ? dot : "var(--border)",
      }} />
      {c.label}
    </span>
  );
}

// ---------- Source badge (Reddit / BOCSAR / ArcGIS / OSM / TfNSW) ----------
function SourceBadge({ kind, n, onClick }) {
  const labels = {
    reddit: "Reddit",
    bocsar: "BOCSAR",
    arcgis: "ArcGIS",
    osm: "OSM",
    tfnsw: "TfNSW",
    pdf: "PDF",
  };
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "2px 7px 2px 5px", borderRadius: 4,
        background: "var(--bg-elev)", border: "1px solid var(--border)",
        color: "var(--fg)", fontFamily: "var(--mono)", fontSize: 10.5,
        cursor: "pointer", lineHeight: 1.4,
      }}
    >
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 14, height: 14, borderRadius: 3, background: "var(--fg)",
        color: "var(--bg)", fontSize: 8, fontWeight: 700,
      }}>{(labels[kind] || kind)[0]}</span>
      <span>{labels[kind] || kind}</span>
      {n != null && <span style={{ color: "var(--muted)" }}>·{n}</span>}
    </button>
  );
}

// ---------- Inline citation footnote [n] ----------
function Cite({ n, onHover, onLeave, onClick, active }) {
  return (
    <sup
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      onClick={onClick}
      style={{
        cursor: "pointer", padding: "1px 5px", marginLeft: 2,
        borderRadius: 3, fontFamily: "var(--mono)", fontSize: 10,
        background: active ? "var(--accent)" : "var(--bg-elev)",
        color: active ? "white" : "var(--fg)",
        border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
        lineHeight: 1, position: "relative", top: -1,
        transition: "background 120ms",
      }}
    >{n}</sup>
  );
}

// ---------- Score gauge (small circular) ----------
function ScoreGauge({ value, size = 56, label }) {
  const r = size / 2 - 4;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value)) / 100;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none"
                stroke="var(--border)" strokeWidth={3} />
        <circle cx={size/2} cy={size/2} r={r} fill="none"
                stroke="var(--accent)" strokeWidth={3}
                strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
                strokeLinecap="round" />
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "flex",
        alignItems: "center", justifyContent: "center",
        flexDirection: "column", lineHeight: 1,
      }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: size * 0.32, fontWeight: 600 }}>{value}</div>
        {label && <div style={{ fontSize: 8, color: "var(--muted)", marginTop: 2, fontFamily: "var(--mono)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>}
      </div>
    </div>
  );
}

// ---------- Bar (for aspect / comparator rows) ----------
function Bar({ value, max = 100, color = "var(--accent)", height = 6, bg = "var(--border)" }) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div style={{ position: "relative", height, background: bg, borderRadius: height/2, overflow: "hidden" }}>
      <div style={{ width: `${w}%`, height: "100%", background: color, borderRadius: height/2 }} />
    </div>
  );
}

// ---------- Diverging bar for compare (negative left, positive right) ----------
function DivergingBar({ left, right, max = 100 }) {
  const lw = (left / max) * 50;
  const rw = (right / max) * 50;
  return (
    <div style={{ position: "relative", height: 8, display: "flex", alignItems: "center" }}>
      <div style={{ flex: 1, display: "flex", justifyContent: "flex-end", paddingRight: 1 }}>
        <div style={{
          width: `${lw}%`, height: 8, borderRadius: "4px 0 0 4px",
          background: "oklch(0.55 0.18 25)",
        }} />
      </div>
      <div style={{ width: 1, height: 14, background: "var(--fg)" }} />
      <div style={{ flex: 1, paddingLeft: 1 }}>
        <div style={{
          width: `${rw}%`, height: 8, borderRadius: "0 4px 4px 0",
          background: "oklch(0.55 0.18 285)",
        }} />
      </div>
    </div>
  );
}

// ---------- Mini Sydney map (stylized, schematic) ----------
// Hand-built schematic; not a real map. Polygons highlight active suburbs.
const SUBURB_POLYS = {
  Newtown:    "M150,180 L185,175 L195,200 L180,225 L150,220 Z",
  Redfern:    "M195,200 L235,195 L240,225 L215,240 L180,225 Z",
  Glebe:      "M120,170 L150,180 L150,220 L125,215 Z",
  Surry:      "M215,180 L255,175 L260,205 L235,210 L235,195 Z",
  Waterloo:   "M215,240 L250,235 L255,265 L225,270 Z",
  Marrickville:"M150,220 L180,225 L185,255 L155,260 Z",
};

function MiniMap({ active = [], height = 260, layer = "liveability", interactive = true, onSuburbHover, onSuburbClick }) {
  const layerColors = {
    liveability: { high: "oklch(0.55 0.18 285)", low: "oklch(0.92 0.02 285)" },
    safety:      { high: "oklch(0.55 0.18 25)",  low: "oklch(0.92 0.02 25)" },
    transport:   { high: "oklch(0.55 0.16 235)", low: "oklch(0.92 0.02 235)" },
    lifestyle:   { high: "oklch(0.62 0.16 75)",  low: "oklch(0.92 0.02 75)" },
  };
  const col = layerColors[layer] || layerColors.liveability;
  return (
    <div style={{
      position: "relative", width: "100%", height, borderRadius: 8,
      overflow: "hidden", background: "var(--bg-elev)",
      border: "1px solid var(--border)",
    }}>
      <svg viewBox="0 0 380 320" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        {/* base land hatch */}
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--border)" strokeWidth="0.5" />
          </pattern>
          <pattern id="water" width="10" height="10" patternUnits="userSpaceOnUse">
            <rect width="10" height="10" fill="var(--bg)" />
            <path d="M0 5 Q2.5 3 5 5 T10 5" fill="none" stroke="var(--border)" strokeWidth="0.4" />
          </pattern>
        </defs>
        <rect width="380" height="320" fill="url(#water)" />
        {/* land */}
        <path d="M40,80 L340,60 L360,250 L260,290 L80,280 L30,200 Z"
              fill="var(--bg)" stroke="var(--border)" strokeWidth="0.5" />
        <path d="M40,80 L340,60 L360,250 L260,290 L80,280 L30,200 Z"
              fill="url(#hatch)" opacity="0.4" />
        {/* harbour cut */}
        <path d="M180,60 Q210,90 260,80 Q300,75 320,100"
              fill="none" stroke="var(--border)" strokeWidth="6" opacity="0.5" />
        {/* suburb polygons */}
        {Object.entries(SUBURB_POLYS).map(([name, d]) => {
          const isActive = active.includes(name);
          return (
            <g key={name}>
              <path d={d}
                    fill={isActive ? col.high : col.low}
                    fillOpacity={isActive ? 0.55 : 0.30}
                    stroke={isActive ? col.high : "var(--border)"}
                    strokeWidth={isActive ? 1.5 : 0.6}
                    style={{ cursor: interactive ? "pointer" : "default", transition: "fill-opacity 160ms" }}
                    onMouseEnter={() => interactive && onSuburbHover && onSuburbHover(name)}
                    onMouseLeave={() => interactive && onSuburbHover && onSuburbHover(null)}
                    onClick={() => interactive && onSuburbClick && onSuburbClick(name)} />
              {isActive && (
                <text x={parseFloat(d.split(",")[1])} y={parseFloat(d.split(",")[2])-5}
                      fontFamily="var(--mono)" fontSize="9" fill="var(--fg)" fontWeight="600">
                  {name}
                </text>
              )}
            </g>
          );
        })}
        {/* compass */}
        <g transform="translate(345 30)">
          <circle r="10" fill="var(--bg)" stroke="var(--border)" />
          <text y="3" textAnchor="middle" fontFamily="var(--mono)" fontSize="8" fill="var(--fg)">N</text>
        </g>
      </svg>
      <div style={{
        position: "absolute", bottom: 6, left: 8, fontFamily: "var(--mono)",
        fontSize: 9, color: "var(--muted)", letterSpacing: "0.05em",
      }}>
        layer · {layer}
      </div>
    </div>
  );
}

window.CategoryChip = CategoryChip;
window.SourceBadge = SourceBadge;
window.Cite = Cite;
window.ScoreGauge = ScoreGauge;
window.Bar = Bar;
window.DivergingBar = DivergingBar;
window.MiniMap = MiniMap;
