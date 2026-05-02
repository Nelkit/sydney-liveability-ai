// Direction C — Detailed Report for a single suburb (deep dive)
const { useState: useStateC } = React;

function DirectionC() {
  const name = "Newtown";
  const data = DATA.suburbs[name];
  const aspects = DATA.aspects[name] || [];
  const reddit = DATA.reddit[name] || [];
  const emotions = DATA.emotions[name];
  const crime = DATA.crime[name] || DATA.crime.Glebe;

  const accent = "oklch(0.55 0.18 285)";

  return (
    <div style={{
      width: 1280, height: 1480,
      background: "var(--bg)", color: "var(--fg)",
      fontFamily: "var(--ui)", fontSize: 13,
      border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden",
      display: "flex", flexDirection: "column",
    }}>
      {/* ============ HEADER ============ */}
      <div style={{
        padding: "16px 24px", borderBottom: "1px solid var(--border)",
        display: "flex", alignItems: "center", gap: 16,
      }}>
        <button style={{
          width: 28, height: 28, borderRadius: 6, border: "1px solid var(--border)",
          background: "var(--bg)", cursor: "pointer", display: "flex",
          alignItems: "center", justifyContent: "center",
        }}>
          <svg width="12" height="12" viewBox="0 0 14 14"><path d="M11 7H3m3-3-3 3 3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Detailed report · single suburb</div>
          <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 2 }}>{name} <span style={{ color: "var(--muted)", fontWeight: 400 }}>· {data.sa4}</span></div>
        </div>
        <CategoryChip kind="sentiment" />
        <CategoryChip kind="gis" />
        <CategoryChip kind="crime" />
        <button style={{
          padding: "7px 12px", borderRadius: 6, border: "1px solid var(--border)",
          background: "var(--bg)", cursor: "pointer", fontSize: 11.5, fontWeight: 500,
          display: "flex", alignItems: "center", gap: 6,
        }}>Export PDF</button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
        {/* ============ ASSISTANT RESPONSE (echo) ============ */}
        <SectionCard title="Assistant response" hint="echo of /api/chat answer">
          <div style={{
            display: "flex", gap: 16, alignItems: "flex-start",
            padding: "16px 18px",
            background: "linear-gradient(180deg, oklch(0.99 0.01 285), var(--bg))",
            borderRadius: 8,
          }}>
            <div style={{
              width: 4, alignSelf: "stretch", borderRadius: 2,
              background: accent,
            }}/>
            <div style={{ flex: 1, fontSize: 14, lineHeight: 1.65, letterSpacing: "-0.005em" }}>
              {name} has a facilities score of <b>{data.facilities.toFixed(1)}</b> and a walkability score of <b>{data.walkability.toFixed(1)}</b>. It offers {data.cafes} cafes and {data.restaurants} restaurants. Sentiment analysis indicates that residents have positive feelings towards <b>nightlife</b> (score 0.91) and <b>food &amp; cafes</b> (score 0.88), but express concerns about <b>noise</b> (score 0.22) and <b>affordability</b> (score 0.31), based on Reddit discussions.
            </div>
          </div>
        </SectionCard>

        {/* ============ EXECUTIVE SUMMARY ============ */}
        <SectionCard title="Executive summary" hint="weighted profile applied">
          <div style={{ display: "grid", gridTemplateColumns: "200px 1fr 280px", gap: 24, alignItems: "center" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
              <ScoreGauge value={data.score} size={140} label="liveability" />
              <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>weighted · 0–100</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                { k: "transport", v: data.transport, w: 7 },
                { k: "safety", v: data.safety, w: 8 },
                { k: "lifestyle", v: data.lifestyle, w: 7 },
                { k: "affordability", v: data.affordability, w: 2 },
              ].map((d) => (
                <div key={d.k} style={{ display: "grid", gridTemplateColumns: "100px 1fr 60px 60px", alignItems: "center", gap: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, textTransform: "capitalize" }}>{d.k}</div>
                  <Bar value={d.v} color={accent} height={6} />
                  <div style={{ fontFamily: "var(--mono)", fontSize: 11.5, fontWeight: 600 }}>{d.v}</div>
                  <div style={{
                    fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)",
                    padding: "2px 6px", borderRadius: 4, border: "1px solid var(--border)",
                    textAlign: "center", background: "var(--bg-elev)",
                  }}>w·{d.w}</div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Pill tone="pos" label="LOVED FOR" body="Nightlife" sub="0.91 · 312 mentions" />
              <Pill tone="neg" label="CONCERN" body="Affordability" sub="0.31 · 142 mentions" />
            </div>
          </div>
        </SectionCard>

        {/* ============ ASPECT RADAR + EMOTION PROFILE ============ */}
        <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 16 }}>
          <SectionCard title="Aspect radar" hint={`DeBERTa-v3 · ${aspects.reduce((a,b)=>a+b.mentions,0)} mentions analyzed`}>
            <AspectRadarFull data={aspects} accent={accent} />
          </SectionCard>
          <SectionCard title="Emotion profile" hint="GoEmotions · averaged across posts">
            <EmotionProfile data={emotions} />
          </SectionCard>
        </div>

        {/* ============ CRIME + GIS ============ */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <SectionCard title="Crime breakdown" hint={`BOCSAR · ${data.sa4} SA4 · per 100k · 2024`}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {crime.map((c) => (
                <div key={c.cat} style={{ display: "grid", gridTemplateColumns: "180px 1fr 60px 50px", alignItems: "center", gap: 10 }}>
                  <div style={{ fontSize: 12 }}>{c.cat}</div>
                  <Bar value={c.v} max={500} color="oklch(0.55 0.18 25)" height={6} />
                  <div style={{ fontFamily: "var(--mono)", fontSize: 11.5, fontWeight: 600 }}>{c.v}</div>
                  <div style={{
                    fontFamily: "var(--mono)", fontSize: 10.5, fontWeight: 600,
                    color: c.trend < 0 ? "oklch(0.55 0.16 145)" : "oklch(0.55 0.18 25)",
                    textAlign: "right",
                  }}>{c.trend > 0 ? "+" : ""}{c.trend}%</div>
                </div>
              ))}
            </div>
            <div style={{
              marginTop: 12, padding: "8px 10px", borderRadius: 6,
              background: "var(--bg-elev)", border: "1px solid var(--border)",
              fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)",
              display: "flex", justifyContent: "space-between",
            }}>
              <span>crime_index</span>
              <span style={{ fontWeight: 600, color: "var(--fg)" }}>{data.crimeIdx.toFixed(2)}</span>
            </div>
          </SectionCard>
          <SectionCard title="GIS · facilities" hint="ArcGIS + OSM">
            <MiniMap active={[name]} height={220} layer="liveability" interactive={false} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginTop: 10 }}>
              <Fact label="cafes" v={data.cafes} />
              <Fact label="restaurants" v={data.restaurants} />
              <Fact label="parks" v={data.parks} />
              <Fact label="playgrounds" v={data.playgrounds} />
            </div>
          </SectionCard>
        </div>

        {/* ============ REDDIT HIGHLIGHTS ============ */}
        <SectionCard title="Reddit highlights" hint={`${reddit.length} cited · permalinks preserved`}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            {reddit.map((q) => <RedditQuoteFull key={q.id} q={q} />)}
          </div>
        </SectionCard>

        {/* ============ EVIDENCE TRACE ============ */}
        <SectionCard title="Evidence trace" hint="auditable · pipeline + chunks">
          <EvidenceTrace />
        </SectionCard>
      </div>
    </div>
  );
}

// ---------- Section card ----------
function SectionCard({ title, hint, children }) {
  return (
    <div style={{
      padding: 18, borderRadius: 10,
      border: "1px solid var(--border)", background: "var(--bg)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>{title}</div>
        {hint && <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>{hint}</div>}
      </div>
      {children}
    </div>
  );
}

// ---------- Pill (loved for / concern) ----------
function Pill({ tone, label, body, sub }) {
  const colors = tone === "pos"
    ? { bg: "oklch(0.96 0.04 145)", bd: "oklch(0.85 0.06 145)", fg: "oklch(0.40 0.14 145)" }
    : { bg: "oklch(0.96 0.04 25)", bd: "oklch(0.85 0.06 25)", fg: "oklch(0.45 0.14 25)" };
  return (
    <div style={{
      padding: "10px 12px", borderRadius: 8,
      background: colors.bg, border: `1px solid ${colors.bd}`,
    }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 9.5, color: colors.fg, fontWeight: 600, letterSpacing: "0.08em" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{body}</div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)", marginTop: 1 }}>{sub}</div>
    </div>
  );
}

// ---------- Full aspect radar (bigger version with legend) ----------
function AspectRadarFull({ data, accent }) {
  const size = 320;
  const cx = size / 2, cy = size / 2;
  const rMax = size / 2 - 36;
  const n = data.length;
  const points = data.map((d, i) => {
    const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
    const r = rMax * d.pos;
    return { x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r, ang, label: d.aspect, v: d.pos };
  });
  const polyPath = points.map((p) => `${p.x},${p.y}`).join(" ");
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <svg width={size} height={size}>
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <circle key={f} cx={cx} cy={cy} r={rMax * f} fill="none" stroke="var(--border)" strokeWidth="0.6" />
        ))}
        {data.map((d, i) => {
          const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
          const x = cx + Math.cos(ang) * rMax;
          const y = cy + Math.sin(ang) * rMax;
          return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--border)" strokeWidth="0.5" />;
        })}
        <polygon points={polyPath} fill={accent} fillOpacity="0.15" stroke={accent} strokeWidth="1.5" />
        {points.map((p, i) => {
          const color = p.v >= 0.6 ? "oklch(0.55 0.16 145)" : p.v >= 0.4 ? "oklch(0.65 0.02 250)" : "oklch(0.55 0.18 25)";
          return <circle key={i} cx={p.x} cy={p.y} r="3" fill={color} />;
        })}
        {data.map((d, i) => {
          const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
          const r = rMax + 18;
          const x = cx + Math.cos(ang) * r;
          const y = cy + Math.sin(ang) * r;
          return (
            <g key={i}>
              <text x={x} y={y - 5} fontFamily="var(--ui)" fontSize="11" fontWeight="500" fill="var(--fg)"
                    textAnchor={Math.cos(ang) > 0.3 ? "start" : Math.cos(ang) < -0.3 ? "end" : "middle"}
                    dominantBaseline="middle">
                {d.aspect}
              </text>
              <text x={x} y={y + 7} fontFamily="var(--mono)" fontSize="9.5" fill="var(--muted)"
                    textAnchor={Math.cos(ang) > 0.3 ? "start" : Math.cos(ang) < -0.3 ? "end" : "middle"}
                    dominantBaseline="middle">
                {d.pos.toFixed(2)} · {d.mentions}
              </text>
            </g>
          );
        })}
        <text x={cx} y={cy + 4} fontFamily="var(--mono)" fontSize="10" fill="var(--muted)" textAnchor="middle">LIVEABILITY</text>
      </svg>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
        <Legend />
        <div style={{ height: 1, background: "var(--border)", margin: "4px 0" }} />
        {data.sort((a,b)=>b.pos - a.pos).slice(0,6).map((d) => (
          <div key={d.aspect} style={{ display: "grid", gridTemplateColumns: "1fr 50px", fontSize: 11.5, alignItems: "center", gap: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: d.pos >= 0.6 ? "oklch(0.55 0.16 145)" : d.pos >= 0.4 ? "oklch(0.65 0.02 250)" : "oklch(0.55 0.18 25)" }} />
              <span>{d.aspect}</span>
            </div>
            <span style={{ fontFamily: "var(--mono)", color: "var(--muted)", textAlign: "right" }}>{d.pos.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div style={{ display: "flex", gap: 12, fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 8, height: 8, borderRadius: 999, background: "oklch(0.55 0.16 145)" }}/>positive</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 8, height: 8, borderRadius: 999, background: "oklch(0.65 0.02 250)" }}/>neutral</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 8, height: 8, borderRadius: 999, background: "oklch(0.55 0.18 25)" }}/>negative</span>
    </div>
  );
}

// ---------- Emotion profile ----------
function EmotionProfile({ data }) {
  const colors = {
    joy: "oklch(0.72 0.16 75)",
    surprise: "oklch(0.65 0.16 195)",
    neutral: "oklch(0.65 0.02 250)",
    sadness: "oklch(0.55 0.14 270)",
    fear: "oklch(0.50 0.16 305)",
    anger: "oklch(0.55 0.18 25)",
    disgust: "oklch(0.55 0.16 145)",
  };
  const max = Math.max(...Object.values(data));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Object.entries(data).map(([k, v]) => (
        <div key={k} style={{ display: "grid", gridTemplateColumns: "70px 1fr 30px", alignItems: "center", gap: 10, fontSize: 11.5 }}>
          <div style={{ textTransform: "capitalize" }}>{k}</div>
          <Bar value={v} max={max} color={colors[k]} height={6} />
          <div style={{ fontFamily: "var(--mono)", fontWeight: 600, textAlign: "right" }}>{v}</div>
        </div>
      ))}
    </div>
  );
}

// ---------- Reddit quote (full) ----------
function RedditQuoteFull({ q }) {
  const sentColor = q.sentiment === "pos" ? "oklch(0.55 0.16 145)"
                   : q.sentiment === "neg" ? "oklch(0.55 0.18 25)"
                   : "oklch(0.65 0.02 250)";
  return (
    <div style={{
      padding: 12, borderRadius: 8,
      border: "1px solid var(--border)", background: "var(--bg-elev)",
      borderLeft: `3px solid ${sentColor}`,
      display: "flex", flexDirection: "column", gap: 10,
    }}>
      <div style={{ fontSize: 12.5, lineHeight: 1.55 }}>“{q.q}”</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>
        <span style={{ padding: "1px 6px", borderRadius: 3, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--fg)" }}>
          {q.aspect}
        </span>
        <span style={{ color: sentColor, fontWeight: 600 }}>{q.sentiment}</span>
        <span>↑{q.up}</span>
        <span style={{ flex: 1 }} />
        <a href="#" style={{ color: "var(--muted)", textDecoration: "underline" }}>reddit/{q.id}</a>
      </div>
    </div>
  );
}

// ---------- Evidence trace ----------
function EvidenceTrace() {
  const t = DATA.trace;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Pipeline horizontal */}
      <div style={{ display: "flex", alignItems: "stretch", gap: 0, position: "relative" }}>
        <PipelineNode label="router" sub={t.router.note} ms={t.router.ms} first />
        {t.specialists.map((s, i) => (
          <PipelineNode key={s.id} label={s.id} sub={`${s.store} · ${s.retrieved} chunks`} ms={s.ms} last={i === t.specialists.length - 1} />
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>retrieval</div>
          <RetrievalBar2 label="Reddit · MiniLM"      value={14} max={20} />
          <RetrievalBar2 label="PostGIS facilities"   value={6}  max={20} />
          <RetrievalBar2 label="BOCSAR SA4"           value={2}  max={20} />
          <RetrievalBar2 label="ArcGIS layers"        value={4}  max={20} />
        </div>
        <div style={{
          padding: 12, borderRadius: 8, background: "var(--bg-elev)", border: "1px solid var(--border)",
          fontFamily: "var(--mono)", fontSize: 11, color: "var(--fg)", lineHeight: 1.7,
        }}>
          <div style={{ color: "var(--muted)", marginBottom: 4 }}>quality.evidence_trace_summary</div>
          <div>route: <span style={{ color: "oklch(0.45 0.14 285)" }}>sentiment · gis · crime</span></div>
          <div>chunks_total: 26 · stores: 4</div>
          <div>latency_ms: 1916 · model: crew/synth-v0.4</div>
          <div>grounded: <span style={{ color: "oklch(0.45 0.14 145)" }}>✓ all claims cited</span></div>
        </div>
      </div>
    </div>
  );
}

function PipelineNode({ label, sub, ms, first, last }) {
  return (
    <div style={{
      flex: 1, padding: "12px 14px",
      border: "1px solid var(--border)",
      borderRight: last ? "1px solid var(--border)" : "none",
      borderLeft: first ? "1px solid var(--border)" : "none",
      borderRadius: first ? "8px 0 0 8px" : last ? "0 8px 8px 0" : 0,
      background: "var(--bg-elev)", position: "relative",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--accent)" }} />
        <span style={{ fontFamily: "var(--mono)", fontSize: 11.5, fontWeight: 600 }}>{label}</span>
      </div>
      <div style={{ fontSize: 10.5, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{sub}</div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)", marginTop: 4 }}>{ms}ms</div>
      {!last && (
        <div style={{
          position: "absolute", right: -7, top: "50%", transform: "translateY(-50%)", zIndex: 2,
          width: 14, height: 14, borderRadius: 999, background: "var(--bg)",
          border: "1px solid var(--border)", display: "flex",
          alignItems: "center", justifyContent: "center",
        }}>
          <svg width="8" height="8" viewBox="0 0 14 14"><path d="M5 4l3 3-3 3" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" /></svg>
        </div>
      )}
    </div>
  );
}

function RetrievalBar2({ label, value, max }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
        <span>{label}</span>
        <span style={{ fontFamily: "var(--mono)", color: "var(--muted)" }}>{value}/{max}</span>
      </div>
      <Bar value={value} max={max} height={4} />
    </div>
  );
}

window.DirectionC = DirectionC;
