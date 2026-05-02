// Direction A — Evidence-first chat with map sync + evidence drawer
const { useState: useStateA, useEffect: useEffectA, useMemo: useMemoA, useRef: useRefA } = React;

function DirectionA() {
  const [activeSuburbs, setActiveSuburbs] = useStateA(["Glebe", "Newtown"]);
  const [hoverSuburb, setHoverSuburb] = useStateA(null);
  const [hoverCite, setHoverCite] = useStateA(null);
  const [openTrace, setOpenTrace] = useStateA(true);
  const [layer, setLayer] = useStateA("liveability");
  const [input, setInput] = useStateA("");

  // The conversation we render.
  const messages = [
    {
      role: "user",
      text: "I work in CBD and want a quiet, walkable suburb under $700/wk. Should I look at Glebe or Newtown?",
      ts: "10:42",
    },
    {
      role: "assistant",
      ts: "10:42",
      router: {
        categories: ["sentiment", "gis", "comparator"],
        suburbs: ["Glebe", "Newtown"],
        latencyMs: 1916,
      },
      // Each claim references citations [n]; on hover we highlight the source
      // and the polygon on the map.
      claims: [
        {
          text: "Both are inner-west suburbs with strong walkability — Newtown scores 88.2 and Glebe 84.1",
          cites: [{ n: 1, src: "arcgis", suburbs: ["Newtown", "Glebe"], detail: "ArcGIS facilities + OSM walkability index" }],
        },
        {
          text: "but their character is different. Newtown is louder and more nightlife-driven (nightlife sentiment 0.91, noise sentiment 0.22)",
          cites: [{ n: 2, src: "reddit", suburbs: ["Newtown"], detail: "DeBERTa-v3 ABSA · 484 Reddit posts" }],
        },
        {
          text: "while Glebe leans community + green space (community 0.84, green space 0.79).",
          cites: [{ n: 3, src: "reddit", suburbs: ["Glebe"], detail: "DeBERTa-v3 ABSA · 174 Reddit posts" }],
        },
        {
          text: "On safety, Glebe has materially lower assault rates (281 vs 412 per 100k) and a downward trend",
          cites: [{ n: 4, src: "bocsar", suburbs: ["Glebe", "Newtown"], detail: "BOCSAR · Inner West SA4 · 2024" }],
        },
        {
          text: "— if 'quiet' is the priority, Glebe is the better fit; for cafes and restaurants, Newtown wins on density.",
          cites: [],
        },
      ],
      summary: {
        recommend: "Glebe",
        why: "lower noise, lower crime, comparable walkability",
      },
    },
  ];

  // Map suburbs to highlight: union of claim hover + active.
  const polysActive = hoverCite?.suburbs?.length
    ? hoverCite.suburbs
    : (hoverSuburb ? [hoverSuburb] : activeSuburbs);

  // ---- styles ----
  const wrap = {
    width: 1280, height: 820,
    display: "grid", gridTemplateColumns: "440px 1fr 320px",
    background: "var(--bg)", color: "var(--fg)",
    fontFamily: "var(--ui)", fontSize: 13,
    border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden",
  };

  return (
    <div style={wrap}>
      {/* ============ COL 1 — CHAT ============ */}
      <div style={{ display: "flex", flexDirection: "column", borderRight: "1px solid var(--border)", background: "var(--bg)" }}>
        <Header />
        <div style={{ flex: 1, overflow: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
          {messages.map((m, i) =>
            m.role === "user"
              ? <UserBubble key={i} m={m} />
              : <AssistantBubble
                  key={i}
                  m={m}
                  hoverCite={hoverCite}
                  setHoverCite={setHoverCite}
                />
          )}
        </div>
        <ChatInput value={input} onChange={setInput} />
      </div>

      {/* ============ COL 2 — MAP ============ */}
      <div style={{ position: "relative", background: "var(--bg-elev)" }}>
        <MapHeader layer={layer} setLayer={setLayer} active={polysActive} />
        <MiniMap
          active={polysActive}
          height={820 - 56}
          layer={layer}
          interactive={true}
          onSuburbHover={setHoverSuburb}
          onSuburbClick={(s) => setActiveSuburbs([s])}
        />
        {/* Bottom score rail */}
        <ScoreRail
          suburbs={Object.keys(DATA.suburbs)}
          active={activeSuburbs[0]}
          onClick={(s) => setActiveSuburbs([s])}
        />
      </div>

      {/* ============ COL 3 — EVIDENCE DRAWER ============ */}
      <EvidenceDrawer
        open={openTrace}
        setOpen={setOpenTrace}
        trace={DATA.trace}
        hoverCite={hoverCite}
        messages={messages}
      />
    </div>
  );
}

// ---------- Header ----------
function Header() {
  return (
    <div style={{
      height: 52, padding: "0 20px", display: "flex", alignItems: "center",
      justifyContent: "space-between", borderBottom: "1px solid var(--border)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Logo />
        <div style={{ fontWeight: 600, letterSpacing: "-0.01em" }}>Liveability AI</div>
        <span style={{
          fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)",
          padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 4,
        }}>v0.4.2</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button style={iconBtnStyle} title="History"><Icon name="clock" /></button>
        <button style={iconBtnStyle} title="New chat"><Icon name="plus" /></button>
      </div>
    </div>
  );
}

function Logo() {
  return (
    <div style={{
      width: 24, height: 24, borderRadius: 6, background: "var(--fg)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <svg width="14" height="14" viewBox="0 0 14 14">
        <path d="M7 1 L13 11 L7 9 L1 11 Z" fill="var(--bg)" />
      </svg>
    </div>
  );
}

const iconBtnStyle = {
  width: 28, height: 28, borderRadius: 6, border: "1px solid var(--border)",
  background: "var(--bg)", color: "var(--fg)", display: "flex",
  alignItems: "center", justifyContent: "center", cursor: "pointer",
};

function Icon({ name, size = 14 }) {
  const paths = {
    clock: <><circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M7 4v3l2 1" stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round" /></>,
    plus: <path d="M7 3v8M3 7h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />,
    arrow: <path d="M3 7h8m-3-3 3 3-3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />,
    chevron: <path d="M5 4l3 3-3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />,
    close: <path d="M3.5 3.5l7 7m0-7-7 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />,
    book: <><path d="M2 3h4a2 2 0 0 1 2 2v7H4a2 2 0 0 1-2-2z" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M12 3H8a2 2 0 0 0-2 2v7h4a2 2 0 0 0 2-2z" fill="none" stroke="currentColor" strokeWidth="1.2" /></>,
    layers: <><path d="M7 1L1 4l6 3 6-3z" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M1 7l6 3 6-3" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M1 10l6 3 6-3" fill="none" stroke="currentColor" strokeWidth="1.2" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 14 14">{paths[name]}</svg>;
}

// ---------- User bubble ----------
function UserBubble({ m }) {
  return (
    <div style={{ alignSelf: "flex-end", maxWidth: "92%", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
      <div style={{
        padding: "12px 14px", borderRadius: 12, background: "var(--fg)",
        color: "var(--bg)", fontSize: 13.5, lineHeight: 1.55, letterSpacing: "-0.005em",
      }}>{m.text}</div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>you · {m.ts}</div>
    </div>
  );
}

// ---------- Assistant bubble ----------
function AssistantBubble({ m, hoverCite, setHoverCite }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Router chips */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginRight: 4 }}>route</span>
        {m.router.categories.map((c) => <CategoryChip key={c} kind={c} />)}
        <span style={{ flex: 1 }} />
        <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>
          {m.router.suburbs.map((s) => `@${s}`).join(" · ")} · {m.router.latencyMs}ms
        </span>
      </div>
      {/* Answer body */}
      <div style={{
        padding: 16, borderRadius: 12, border: "1px solid var(--border)",
        background: "var(--bg)", fontSize: 13.5, lineHeight: 1.65, letterSpacing: "-0.005em",
      }}>
        {m.claims.map((cl, i) => (
          <span key={i}>
            {cl.text}
            {cl.cites.map((c) => (
              <Cite key={c.n}
                    n={c.n}
                    active={hoverCite?.n === c.n}
                    onHover={() => setHoverCite(c)}
                    onLeave={() => setHoverCite(null)} />
            ))}
            {i < m.claims.length - 1 ? " " : ""}
          </span>
        ))}

        {/* Recommendation card */}
        {m.summary && (
          <div style={{
            marginTop: 14, padding: 12, borderRadius: 8,
            background: "linear-gradient(180deg, oklch(0.97 0.025 285), oklch(0.99 0.01 285))",
            border: "1px solid oklch(0.88 0.05 285)",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8, background: "var(--accent)",
              color: "white", display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: "var(--mono)", fontSize: 14, fontWeight: 600, letterSpacing: "-0.02em",
            }}>★</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "var(--mono)", fontSize: 9.5, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Recommendation</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 1 }}>{m.summary.recommend}</div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 1 }}>{m.summary.why}</div>
            </div>
            <button style={{
              padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)",
              background: "var(--bg)", color: "var(--fg)", cursor: "pointer",
              fontSize: 11.5, fontWeight: 500, display: "flex", alignItems: "center", gap: 6,
            }}>Open report <Icon name="arrow" /></button>
          </div>
        )}
      </div>

      {/* Sources strip */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginRight: 2 }}>sources</span>
        <SourceBadge kind="reddit" n={658} />
        <SourceBadge kind="bocsar" n={2} />
        <SourceBadge kind="arcgis" n={4} />
        <SourceBadge kind="osm" n={11} />
        <span style={{ flex: 1 }} />
        <FeedbackBtn />
      </div>
    </div>
  );
}

function FeedbackBtn() {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      <button style={{ ...iconBtnStyle, width: 24, height: 24 }} title="Helpful">
        <svg width="11" height="11" viewBox="0 0 14 14"><path d="M3 6h2v6H3zm3 0v6h4l1.5-4-1-2H8V3a1 1 0 0 0-2 0z" fill="none" stroke="currentColor" strokeWidth="1.2" /></svg>
      </button>
      <button style={{ ...iconBtnStyle, width: 24, height: 24 }} title="Not helpful">
        <svg width="11" height="11" viewBox="0 0 14 14" style={{transform:"rotate(180deg)"}}><path d="M3 6h2v6H3zm3 0v6h4l1.5-4-1-2H8V3a1 1 0 0 0-2 0z" fill="none" stroke="currentColor" strokeWidth="1.2" /></svg>
      </button>
    </div>
  );
}

// ---------- Chat input ----------
function ChatInput({ value, onChange }) {
  const suggestions = [
    "is Newtown safe at night?",
    "best cafes in Glebe?",
    "Redfern transport links",
    "compare Newtown vs Glebe",
  ];
  return (
    <div style={{ borderTop: "1px solid var(--border)", padding: "12px 16px 16px" }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
        {suggestions.map((s) => (
          <button key={s} style={{
            padding: "5px 10px", borderRadius: 999, border: "1px solid var(--border)",
            background: "var(--bg-elev)", color: "var(--fg)", cursor: "pointer",
            fontSize: 11, fontFamily: "var(--ui)",
          }}>{s}</button>
        ))}
      </div>
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "8px 8px 8px 14px", borderRadius: 10,
        border: "1px solid var(--border)", background: "var(--bg)",
        boxShadow: "0 1px 0 oklch(0.96 0.005 250)",
      }}>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Ask about transport, safety, vibes…"
          style={{
            flex: 1, border: "none", outline: "none", background: "transparent",
            fontSize: 13.5, fontFamily: "var(--ui)", color: "var(--fg)",
          }}
        />
        <button style={{
          width: 32, height: 32, borderRadius: 8, border: "none",
          background: "var(--fg)", color: "var(--bg)",
          display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer",
        }}>
          <Icon name="arrow" />
        </button>
      </div>
      <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>
        <span>13,500+ docs · BOCSAR · ArcGIS · Reddit</span>
        <span>cited · grounded</span>
      </div>
    </div>
  );
}

// ---------- Map header ----------
function MapHeader({ layer, setLayer, active }) {
  const layers = ["liveability", "safety", "transport", "lifestyle"];
  return (
    <div style={{
      position: "absolute", top: 12, left: 12, right: 12, zIndex: 5,
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 4, padding: 3,
        borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)",
        boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
      }}>
        {layers.map((l) => (
          <button key={l} onClick={() => setLayer(l)}
            style={{
              padding: "5px 10px", borderRadius: 6, border: "none", cursor: "pointer",
              background: layer === l ? "var(--fg)" : "transparent",
              color: layer === l ? "var(--bg)" : "var(--fg)",
              fontSize: 11.5, fontFamily: "var(--ui)", fontWeight: 500, textTransform: "capitalize",
            }}>{l}</button>
        ))}
      </div>
      <div style={{
        padding: "5px 10px", borderRadius: 6,
        background: "var(--bg)", border: "1px solid var(--border)",
        fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)",
      }}>{active.length} suburb{active.length !== 1 ? "s" : ""} active</div>
    </div>
  );
}

// ---------- Score rail ----------
function ScoreRail({ suburbs, active, onClick }) {
  const sorted = suburbs
    .map((s) => ({ s, v: DATA.suburbs[s].score }))
    .sort((a, b) => b.v - a.v);
  return (
    <div style={{
      position: "absolute", bottom: 12, left: 12, right: 12, zIndex: 5,
      display: "flex", gap: 6, padding: 6, borderRadius: 10,
      background: "var(--bg)", border: "1px solid var(--border)",
      boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
    }}>
      {sorted.map(({ s, v }, i) => {
        const isActive = s === active;
        return (
          <button key={s} onClick={() => onClick(s)}
            style={{
              flex: 1, padding: "8px 10px", borderRadius: 6, cursor: "pointer",
              background: isActive ? "var(--fg)" : "transparent",
              color: isActive ? "var(--bg)" : "var(--fg)",
              border: "none", textAlign: "left", display: "flex", flexDirection: "column", gap: 4,
            }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
              <span style={{ fontFamily: "var(--mono)", fontSize: 9.5, opacity: 0.7 }}>#{i+1}</span>
              <span style={{ fontFamily: "var(--mono)", fontSize: 13, fontWeight: 600 }}>{v}</span>
            </div>
            <div style={{ fontSize: 11.5, fontWeight: 500 }}>{s}</div>
            <Bar value={v} bg={isActive ? "rgba(255,255,255,0.18)" : "var(--border)"} color={isActive ? "white" : "var(--accent)"} height={3} />
          </button>
        );
      })}
    </div>
  );
}

// ---------- Evidence drawer ----------
function EvidenceDrawer({ open, setOpen, trace, hoverCite, messages }) {
  return (
    <div style={{
      borderLeft: "1px solid var(--border)", background: "var(--bg)",
      display: "flex", flexDirection: "column", overflow: "hidden",
    }}>
      <div style={{
        height: 52, padding: "0 16px", display: "flex", alignItems: "center",
        justifyContent: "space-between", borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon name="book" />
          <div style={{ fontWeight: 600 }}>Evidence trail</div>
        </div>
        <span style={{
          fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)",
          padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 4,
        }}>auditable</span>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 14, display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Pipeline */}
        <Section title="Pipeline">
          <PipelineRow label="router" sub={trace.router.note} ms={trace.router.ms} />
          {trace.specialists.map((s) => (
            <PipelineRow key={s.id} label={s.id} sub={`${s.store} · ${s.retrieved} chunks`} ms={s.ms} />
          ))}
        </Section>

        {/* Active citation detail */}
        <Section title={hoverCite ? `Citation [${hoverCite.n}]` : "Citations"}>
          {hoverCite ? (
            <div style={{
              padding: 10, borderRadius: 8, border: "1px solid oklch(0.88 0.05 285)",
              background: "oklch(0.98 0.015 285)",
              display: "flex", flexDirection: "column", gap: 8,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <SourceBadge kind={hoverCite.src} />
                {hoverCite.suburbs.map((s) => (
                  <span key={s} style={{
                    fontFamily: "var(--mono)", fontSize: 10, padding: "2px 6px",
                    borderRadius: 4, background: "var(--accent)", color: "white",
                  }}>@{s}</span>
                ))}
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.5, color: "var(--fg)" }}>{hoverCite.detail}</div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)" }}>
                Hover ON · polygon highlighted on map
              </div>
            </div>
          ) : (
            messages.flatMap((m) => m.claims || []).flatMap((cl) => cl.cites).map((c) => (
              <button key={c.n} style={{
                width: "100%", textAlign: "left",
                padding: "8px 10px", borderRadius: 6, border: "1px solid var(--border)",
                background: "var(--bg)", cursor: "pointer", display: "flex",
                alignItems: "center", gap: 8,
              }}>
                <span style={{
                  width: 20, textAlign: "center", fontFamily: "var(--mono)",
                  fontSize: 10.5, color: "var(--muted)",
                }}>[{c.n}]</span>
                <SourceBadge kind={c.src} />
                <span style={{ flex: 1, fontSize: 11.5, color: "var(--fg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {c.detail}
                </span>
              </button>
            ))
          )}
        </Section>

        <Section title="Retrieval breakdown">
          <RetrievalBar label="Reddit · MiniLM" value={14} max={20} />
          <RetrievalBar label="PostGIS facilities" value={6} max={20} />
          <RetrievalBar label="BOCSAR SA4" value={2} max={20} />
          <RetrievalBar label="ArcGIS layers" value={4} max={20} />
        </Section>

        <div style={{
          padding: 10, borderRadius: 6, background: "var(--bg-elev)",
          border: "1px solid var(--border)",
          fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)",
          lineHeight: 1.55,
        }}>
          quality.evidence_trace_summary <br/>
          → router(12ms) → sentiment(612ms) <br/>
          → gis(184ms) → synth(1108ms)<br/>
          total: 1916ms · 26 chunks
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{
        fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)",
        textTransform: "uppercase", letterSpacing: "0.08em",
      }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{children}</div>
    </div>
  );
}

function PipelineRow({ label, sub, ms }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "8px 10px", borderRadius: 6, border: "1px solid var(--border)",
      background: "var(--bg-elev)",
    }}>
      <div style={{
        width: 6, height: 6, borderRadius: 999, background: "var(--accent)",
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11.5, fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 10.5, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{sub}</div>
      </div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)" }}>{ms}ms</div>
    </div>
  );
}

function RetrievalBar({ label, value, max }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
        <span>{label}</span>
        <span style={{ fontFamily: "var(--mono)", color: "var(--muted)" }}>{value}/{max}</span>
      </div>
      <Bar value={value} max={max} height={4} />
    </div>
  );
}

window.DirectionA = DirectionA;
