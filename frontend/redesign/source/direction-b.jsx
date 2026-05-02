// Direction B — Comparator split view + Detailed Report
const { useState: useStateB } = React;

function DirectionB({ layout = "split" /* "split" | "rows" */ }) {
  const [hoverDim, setHoverDim] = useStateB(null);
  const A = "Newtown";
  const B = "Glebe";
  const sa = DATA.suburbs[A];
  const sb = DATA.suburbs[B];

  return (
    <div style={{
      width: 1280, height: 820, background: "var(--bg)",
      color: "var(--fg)", fontFamily: "var(--ui)", fontSize: 13,
      border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden",
      display: "flex", flexDirection: "column",
    }}>
      <CompareHeader A={A} B={B} sa={sa} sb={sb} />

      <div style={{ flex: 1, overflow: "auto" }}>
        {layout === "split" ? (
          <SplitLayout A={A} B={B} sa={sa} sb={sb} hoverDim={hoverDim} setHoverDim={setHoverDim} />
        ) : (
          <RowsLayout A={A} B={B} sa={sa} sb={sb} />
        )}
      </div>
    </div>
  );
}

// ---------- Header ----------
function CompareHeader({ A, B, sa, sb }) {
  const winner = sa.score > sb.score ? A : B;
  const delta = Math.abs(sa.score - sb.score);
  return (
    <div style={{
      padding: "16px 24px", borderBottom: "1px solid var(--border)",
      display: "flex", alignItems: "center", gap: 16, background: "var(--bg)",
    }}>
      <button style={{
        width: 28, height: 28, borderRadius: 6, border: "1px solid var(--border)",
        background: "var(--bg)", cursor: "pointer", display: "flex",
        alignItems: "center", justifyContent: "center",
      }}>
        <svg width="12" height="12" viewBox="0 0 14 14"><path d="M11 7H3m3-3-3 3 3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
      </button>
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Detailed report · comparator</div>
        <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.015em", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "oklch(0.55 0.18 285)" }}>{A}</span>
          <span style={{ fontFamily: "var(--mono)", fontWeight: 400, color: "var(--muted)", fontSize: 13 }}>vs</span>
          <span style={{ color: "oklch(0.62 0.16 75)" }}>{B}</span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <CategoryChip kind="comparator" />
        <CategoryChip kind="sentiment" />
        <CategoryChip kind="gis" />
        <CategoryChip kind="crime" />
      </div>

      <div style={{
        padding: "6px 12px", borderRadius: 8,
        background: "linear-gradient(180deg, oklch(0.97 0.025 285), oklch(0.99 0.01 285))",
        border: "1px solid oklch(0.88 0.05 285)",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>verdict</span>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{winner}</span>
        <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--accent)", fontWeight: 600 }}>+{delta}</span>
      </div>
    </div>
  );
}

// ---------- Split layout (selected option) ----------
function SplitLayout({ A, B, sa, sb, hoverDim, setHoverDim }) {
  const dimensions = [
    { key: "transport",     label: "Transport",     icon: "🚆" },
    { key: "safety",        label: "Safety",        icon: "🛡" },
    { key: "lifestyle",     label: "Lifestyle",     icon: "☕" },
    { key: "affordability", label: "Affordability", icon: "$"  },
  ];

  const accentA = "oklch(0.55 0.18 285)";
  const accentB = "oklch(0.62 0.16 75)";

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
      {/* Top hero — both maps, both gauges, balanced */}
      <SuburbHero name={A} data={sa} accent={accentA} side="left" />
      <SuburbHero name={B} data={sb} accent={accentB} side="right" />

      {/* Center divider with delta dimension labels */}
      <div style={{
        gridColumn: "1 / 3",
        padding: "20px 32px", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)",
        background: "var(--bg-elev)",
      }}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginBottom: 14,
        }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>head-to-head · weighted score 0–100</div>
          <div style={{ display: "flex", alignItems: "center", gap: 16, fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted)" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: accentA }} />{A}
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: accentB }} />{B}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {dimensions.map((d) => {
            const va = sa[d.key], vb = sb[d.key];
            const win = va > vb ? "A" : (vb > va ? "B" : "tie");
            return (
              <div key={d.key}
                   onMouseEnter={() => setHoverDim(d.key)}
                   onMouseLeave={() => setHoverDim(null)}
                   style={{
                     display: "grid", gridTemplateColumns: "60px 1fr 120px 1fr 60px",
                     alignItems: "center", gap: 12,
                     padding: "8px 10px", borderRadius: 8,
                     background: hoverDim === d.key ? "var(--bg)" : "transparent",
                     cursor: "default",
                   }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600, color: win === "A" ? accentA : "var(--muted)", textAlign: "right" }}>{va}</div>
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div style={{
                    width: `${va}%`, height: 10, borderRadius: "4px 0 0 4px",
                    background: win === "A" ? accentA : "oklch(0.85 0.05 285)",
                  }} />
                </div>
                <div style={{ textAlign: "center", fontSize: 12, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                  <span style={{ fontSize: 12 }}>{d.icon}</span>
                  <span>{d.label}</span>
                </div>
                <div>
                  <div style={{
                    width: `${vb}%`, height: 10, borderRadius: "0 4px 4px 0",
                    background: win === "B" ? accentB : "oklch(0.88 0.04 75)",
                  }} />
                </div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600, color: win === "B" ? accentB : "var(--muted)" }}>{vb}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Aspect radar + Reddit highlights */}
      <SuburbAspects name={A} data={DATA.aspects[A] || []} reddit={DATA.reddit[A] || []} accent={accentA} side="left" />
      <SuburbAspects name={B} data={DATA.aspects[B] || []} reddit={DATA.reddit[B] || []} accent={accentB} side="right" />
    </div>
  );
}

// ---------- Suburb hero (top of split column) ----------
function SuburbHero({ name, data, accent, side }) {
  const left = side === "left";
  return (
    <div style={{
      padding: 24,
      borderRight: left ? "1px solid var(--border)" : "none",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
        <div style={{
          position: "relative", width: 88, height: 88,
        }}>
          <ScoreGauge value={data.score} size={88} label="liveability" />
          <div style={{
            position: "absolute", inset: -3, borderRadius: 999,
            border: `2px solid ${accent}`, opacity: 0.25,
          }}/>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>{data.sa4}</div>
          <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em", color: accent }}>{name}</div>
          <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Stat label="walkability" v={data.walkability.toFixed(1)} />
            <Stat label="facilities" v={data.facilities.toFixed(1)} />
            <Stat label="sentiment" v={data.sentiment.toFixed(2)} />
          </div>
        </div>
      </div>

      {/* Mini map for this suburb */}
      <MiniMap active={[name]} height={140} layer="liveability" interactive={false} />

      {/* Quick facts */}
      <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        <Fact label="cafes" v={data.cafes} />
        <Fact label="restaurants" v={data.restaurants} />
        <Fact label="parks" v={data.parks} />
        <Fact label="playgrounds" v={data.playgrounds} />
      </div>
    </div>
  );
}

function Stat({ label, v }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 7px", borderRadius: 4,
      border: "1px solid var(--border)", background: "var(--bg-elev)",
      fontFamily: "var(--mono)", fontSize: 10.5,
    }}>
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <span style={{ fontWeight: 600 }}>{v}</span>
    </span>
  );
}

function Fact({ label, v }) {
  return (
    <div style={{
      padding: "10px 10px", borderRadius: 8,
      border: "1px solid var(--border)", background: "var(--bg)",
    }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 9.5, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, fontFamily: "var(--mono)" }}>{v}</div>
    </div>
  );
}

// ---------- Aspect column (bottom of split) ----------
function SuburbAspects({ name, data, reddit, accent, side }) {
  const left = side === "left";
  return (
    <div style={{
      padding: 24,
      borderRight: left ? "1px solid var(--border)" : "none",
      display: "flex", flexDirection: "column", gap: 16,
    }}>
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>aspect sentiment · DeBERTa-v3</div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>{data.reduce((a,b)=>a+b.mentions,0)} mentions</div>
        </div>
        <AspectRadar data={data} accent={accent} />
      </div>

      <div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>reddit highlights</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {reddit.slice(0,3).map((r) => <RedditQuote key={r.id} q={r} accent={accent} />)}
        </div>
      </div>
    </div>
  );
}

// ---------- Aspect radar ----------
function AspectRadar({ data, accent }) {
  const size = 240;
  const cx = size / 2, cy = size / 2;
  const rMax = size / 2 - 30;
  const n = data.length;
  const points = data.map((d, i) => {
    const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
    const r = rMax * d.pos;
    return { x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r, ang, label: d.aspect, v: d.pos };
  });
  const polyPath = points.map((p) => `${p.x},${p.y}`).join(" ");
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <svg width={size} height={size}>
        {/* grid rings */}
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <circle key={f} cx={cx} cy={cy} r={rMax * f} fill="none" stroke="var(--border)" strokeWidth="0.6" />
        ))}
        {/* axes */}
        {data.map((d, i) => {
          const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
          const x = cx + Math.cos(ang) * rMax;
          const y = cy + Math.sin(ang) * rMax;
          return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--border)" strokeWidth="0.5" />;
        })}
        {/* polygon */}
        <polygon points={polyPath} fill={accent} fillOpacity="0.15" stroke={accent} strokeWidth="1.5" />
        {/* points */}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="2.5" fill={accent} />
        ))}
        {/* labels */}
        {data.map((d, i) => {
          const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
          const r = rMax + 14;
          const x = cx + Math.cos(ang) * r;
          const y = cy + Math.sin(ang) * r;
          return (
            <text key={i} x={x} y={y} fontFamily="var(--mono)" fontSize="9.5" fill="var(--muted)"
                  textAnchor={Math.cos(ang) > 0.3 ? "start" : Math.cos(ang) < -0.3 ? "end" : "middle"}
                  dominantBaseline="middle">
              {d.aspect}
            </text>
          );
        })}
      </svg>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
        {data.slice(0,4).sort((a,b)=>b.pos-a.pos).map((d) => (
          <div key={d.aspect} style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
              <span>{d.aspect}</span>
              <span style={{ fontFamily: "var(--mono)", color: "var(--muted)" }}>{d.pos.toFixed(2)} · {d.mentions}</span>
            </div>
            <Bar value={d.pos * 100} color={accent} height={4} />
          </div>
        ))}
      </div>
    </div>
  );
}

function RedditQuote({ q, accent }) {
  const sentColor = q.sentiment === "pos" ? "oklch(0.55 0.16 145)"
                   : q.sentiment === "neg" ? "oklch(0.55 0.18 25)"
                   : "oklch(0.65 0.02 250)";
  return (
    <div style={{
      padding: "10px 12px", borderRadius: 8,
      border: "1px solid var(--border)", background: "var(--bg-elev)",
      borderLeft: `3px solid ${sentColor}`,
    }}>
      <div style={{ fontSize: 12, lineHeight: 1.5, color: "var(--fg)" }}>“{q.q}”</div>
      <div style={{
        marginTop: 6, display: "flex", alignItems: "center", gap: 8,
        fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)",
      }}>
        <span style={{ padding: "1px 5px", borderRadius: 3, background: "var(--bg)", border: "1px solid var(--border)" }}>
          {q.aspect}
        </span>
        <span>·</span>
        <span style={{ color: sentColor, fontWeight: 600 }}>{q.sentiment}</span>
        <span>·</span>
        <span>↑{q.up}</span>
        <span style={{ flex: 1 }} />
        <span style={{ textDecoration: "underline" }}>reddit/{q.id}</span>
      </div>
    </div>
  );
}

// ---------- Rows layout (tweak alternative) ----------
function RowsLayout({ A, B, sa, sb }) {
  const accentA = "oklch(0.55 0.18 285)";
  const accentB = "oklch(0.62 0.16 75)";
  const dims = [
    { key: "transport",     label: "Transport",     desc: "TfNSW + walkability" },
    { key: "safety",        label: "Safety",        desc: "BOCSAR · per-100k crime" },
    { key: "lifestyle",     label: "Lifestyle",     desc: "Cafes · restaurants · venues" },
    { key: "affordability", label: "Affordability", desc: "Median rent · listings density" },
  ];
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12 }}>
      {dims.map((d) => (
        <div key={d.key} style={{
          display: "grid",
          gridTemplateColumns: "240px 1fr 1fr",
          gap: 16,
          padding: 16,
          border: "1px solid var(--border)", borderRadius: 10,
          background: "var(--bg)",
        }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, letterSpacing: "-0.01em" }}>{d.label}</div>
            <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>{d.desc}</div>
          </div>
          <DimSide name={A} value={sa[d.key]} accent={accentA} winning={sa[d.key] >= sb[d.key]} />
          <DimSide name={B} value={sb[d.key]} accent={accentB} winning={sb[d.key] >= sa[d.key]} />
        </div>
      ))}
    </div>
  );
}

function DimSide({ name, value, accent, winning }) {
  return (
    <div style={{
      padding: 12, borderRadius: 8,
      background: winning ? `color-mix(in oklch, ${accent} 8%, var(--bg))` : "var(--bg-elev)",
      border: `1px solid ${winning ? accent : "var(--border)"}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontWeight: 500 }}>{name}</span>
        <span style={{ fontFamily: "var(--mono)", fontSize: 14, fontWeight: 600, color: winning ? accent : "var(--fg)" }}>{value}</span>
      </div>
      <Bar value={value} color={accent} height={6} />
    </div>
  );
}

window.DirectionB = DirectionB;
