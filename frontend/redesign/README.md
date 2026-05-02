# Sydney Liveability AI · Redesign Handoff

This folder is a **design specification + reference implementation** for the redesign of `frontend/`. The functionality already exists; this is purely a UI refactor.

## Stack assumptions (your project)
- **Framework**: Next.js 14+ App Router (`frontend/src/app`)
- **Styling**: Tailwind CSS
- **Map**: Leaflet inside `frontend/src/components/liveability/MapPanel.tsx`
- **API contract** (unchanged): `/api/chat` returns `{ answer, sources, suburb_scores, map_state, quality.evidence_trace_summary }`

## What's in this folder

| Path | Purpose |
|---|---|
| `README.md` | This file — start here |
| `DESIGN_TOKENS.md` | Color, type, spacing scale → drop into `tailwind.config.ts` |
| `COMPONENT_MAP.md` | Maps each visual block to the file you need to create or modify |
| `source/*.jsx` | Reference implementation as plain React (inline styles, no Tailwind). Use as the source of truth for layout, hierarchy, copy and component composition. **Port to Tailwind in your codebase** — do not copy `style={{...}}` blocks verbatim. |
| `source/Sydney Liveability AI Redesign.html` | Entry point that wires all `.jsx` files. Open locally to see the design live. |
| `screenshots/` | Visual ground-truth for each direction. Use to verify your port. |

## Three directions delivered

### A · Evidence-first chat (`source/direction-a.jsx`)
Replaces the current chat sidebar + map. Three columns:
- Left: chat with router chips on top of every assistant message, inline footnote citations `[n]` that highlight the cited polygon on hover, source badges and feedback row
- Center: Leaflet map with layer switcher (`liveability / safety / transport / lifestyle`) and a bottom score-rail
- Right: Evidence trail drawer (pipeline timing, retrieval breakdown, `quality.evidence_trace_summary`)

### B · Comparator split (`source/direction-b.jsx`)
Triggers when the router returns `comparator` with 2 suburbs. Header + two columns:
- Per-suburb hero (gauge, mini-map, walkability/facilities/sentiment stats, cafes/restaurants/parks/playgrounds counts)
- Center head-to-head with diverging bars per dimension
- Per-suburb aspect radar (DeBERTa-v3) and Reddit highlights with permalinks
- Tweak: `split` (default) vs `rows` (rows-by-dimension layout)

### C · Detailed Report single suburb (`source/direction-c.jsx`)
Replaces the current `Detailed Report` page. Vertical scroll:
1. Header with breadcrumb + router chips + Export PDF
2. Assistant response echo
3. Executive summary (gauge + weighted dims + Loved/Concern pills)
4. Aspect radar + Emotion profile (GoEmotions)
5. Crime breakdown (BOCSAR) + GIS facilities mini-map
6. Reddit highlights (3-col grid)
7. Evidence trace (horizontal pipeline)

## Implementation order (recommended)

1. Apply `DESIGN_TOKENS.md` to `tailwind.config.ts` — gives you the new color palette and font stack
2. Build the **primitives** from `source/primitives.jsx` (CategoryChip, SourceBadge, Cite, ScoreGauge, Bar, DivergingBar, MiniMap) into `frontend/src/components/ui/`
3. Refactor `MapPanel.tsx` to support `layer` prop and emit hover events upward (needed for citation hover sync)
4. Port Direction A first (the main chat experience)
5. Port Direction C (single-suburb report) — reuses primitives
6. Port Direction B (comparator) last — most layout work

## Important notes for the porter

- **Inline styles in `source/*.jsx` are NOT meant to be copied**. They exist because the reference is a single-file HTML preview. Convert them to Tailwind classes using the tokens in `DESIGN_TOKENS.md`.
- **`MiniMap` in primitives.jsx is a stylized SVG**, not a real map. Replace with your real Leaflet `<MapPanel>` configured per the props that direction passes.
- **`data.jsx` is mock data**. Use it only to understand the shapes the components consume. Wire to your real `/api/chat` response.
- **Don't port `design-canvas.jsx` or `tweaks-panel.jsx`** — those are preview infrastructure.
- The `useTweaks` hook used in the HTML preview maps conceptually to a runtime config; in production you can drop the tweak entirely or expose it as a user setting.

## Out of scope (intentionally not redesigned)
- Onboarding (weighting profile chat)
- Profile/auth screens
- Hex Overview
- PDF rental upload flow

These can be next phases — see chat thread for further suggestions.
