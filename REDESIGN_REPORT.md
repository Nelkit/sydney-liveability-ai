# Redesign Report · Sydney Liveability AI

*Ported from `frontend/redesign/` by Claude Sonnet 4.6 · May 2026*

---

## ✅ Implemented

### Step 1 — Design Tokens

| Item | File |
|---|---|
| Full color palette (bg, fg, border, accent, accentB, cat.*, sent.*) in OKLCH | `frontend/tailwind.config.ts` |
| Legacy colors preserved (slateBg, slateMuted, etc.) for backward compat | `frontend/tailwind.config.ts` |
| Font families: Inter (--font-sans) + JetBrains Mono (--font-mono) | `frontend/tailwind.config.ts` |
| Inter + JetBrains Mono loaded via `next/font/google` with CSS variables | `frontend/src/app/layout.tsx` |
| Shadow utilities: float, floatLg | `frontend/tailwind.config.ts` |

### Step 2 — Shared Primitives

| Component | File | Notes |
|---|---|---|
| `CitationHoverContext` | `frontend/src/context/CitationHoverContext.tsx` | Provides `{ hoveredCite, setHoveredCite }` |
| `CategoryChip` | `frontend/src/components/ui/CategoryChip.tsx` | Props: `kind`, `active?`, `size?` — uses OKLCH colors per kind |
| `SourceBadge` | `frontend/src/components/ui/SourceBadge.tsx` | Props: `kind`, `n?`, `onClick?` |
| `Cite` | `frontend/src/components/ui/Cite.tsx` | Writes to CitationHoverContext on hover; shows confidence dot (🟢/🟡/🔴) based on `retrieved` count |
| `ScoreGauge` | `frontend/src/components/ui/ScoreGauge.tsx` | Circular SVG gauge |
| `Bar` + `DivergingBar` | `frontend/src/components/ui/Bar.tsx` | Both variants in one file |
| `Pill` | `frontend/src/components/ui/Pill.tsx` | pos/neg tones for Loved / Concern |
| `SectionCard` | `frontend/src/components/ui/SectionCard.tsx` | Mono uppercase title + hint header |

### Step 3 — TypeScript Types

| Item | File |
|---|---|
| Full `ChatAPIResponse`, `AssistantMessage`, `RouterMeta`, `SuburbScore`, `AspectScore`, `EmotionProfile`, `RedditHighlight`, `CrimeRow`, `EvidenceTrace`, `Citation`, `Claim`, `SourceKind`, `RouterCategory` | `frontend/src/types/api.ts` |

### Step 4 — MapPanel Updates

| Feature | Detail |
|---|---|
| `activeSuburbs: string[]` prop | Highlights named suburbs with higher opacity |
| `hoveredSuburb?: string | null` prop + `onSuburbHover` callback | Polygon mouseover events emitted upward |
| `CitationHoverContext` subscription | When `hoveredCite` is set, `citationActiveSuburbs` are highlighted on the map |
| Label collision fix | Suburb name labels only rendered for active/cited suburbs at normal zoom; all labels shown only at zoom ≥ 15 |
| Dynamic map legend per layer | Gradient changes color per layer (violet/red-orange/blue/amber) |
| Skeleton loading cards | `bg-bg-elev` skeleton cards while civic data loads |
| Layer switcher redesigned | Matches Direction A `MapHeader` style (tab-style buttons inside a pill container) |

### Step 5 — ChatBubbles

| Component | File | Features |
|---|---|---|
| `UserBubble` | `frontend/src/components/liveability/ChatBubbles.tsx` | Dark background bubble + mono timestamp |
| `AssistantBubble` | same | Router chips row, inline `<Cite>` footnotes, grouped source badges (×n deduplication), recommendation card, feedback buttons, follow-up chips |
| `OutOfScopeState` | same | Friendly empty state with suburb suggestion chips |
| `TypingBubble` | same | 3-dot bounce animation |
| `AssistantBubbleSkeleton` | same | Structured skeleton matching bubble layout |

### Step 6 — ChatInput

| Feature | File |
|---|---|
| 4 suggestion chips (crime, gis, sentiment, comparator) | `frontend/src/components/liveability/ChatInput.tsx` |
| AbortController-wired "Stop" cancel button (appears after 3s) | same |
| PDF upload CTA (promoted to footer row) | same |
| Send on Enter | same |
| Auto-focus on mount | same |

### Step 7 — EvidenceDrawer

| Feature | File |
|---|---|
| Pipeline section with `PipelineRow` per specialist | `frontend/src/components/liveability/EvidenceDrawer.tsx` |
| Active citation detail panel (subscribed to CitationHoverContext) | same |
| Retrieval breakdown bars | same |
| "Last updated" per source (BOCSAR: 2024, ArcGIS: live, Reddit: red placeholder) | same |
| Red placeholder when structured trace not returned | same |

### Step 8 — Direction A (Main Page)

| Feature | File |
|---|---|
| 3-column grid: `[440px] [1fr] [320px]` | `frontend/src/app/page.tsx` |
| `CitationHoverProvider` wraps entire app | same |
| `AssistantBubble` fully wired to parsed API response | same |
| AbortController with 3s cancel timer | same |
| Out-of-scope detection from `router.categories` | same |
| Follow-up chips after each assistant response | same |
| Active suburbs passed to `MapPanel` from router response | same |
| New-chat button clears messages | same |
| `EvidenceDrawer` in col 3, receiving last payload trace | same |
| Backward compat: old `AssistantSidebar` / `DetailedReportModal` removed from 3-col layout; onboarding flow preserved | same |

### Step 9 — Direction C (Suburb Report)

| Component | File |
|---|---|
| `app/report/[suburb]/page.tsx` | `frontend/src/app/report/[suburb]/page.tsx` |
| Header with breadcrumb, router chips, Export PDF button | same |
| Assistant response echo | same |
| Executive summary: `ScoreGauge` + weighted dimension bars + `Pill` loved/concern | same |
| `AspectRadar` (lg size) + `EmotionProfile` | `frontend/src/components/report/AspectRadar.tsx`, `EmotionProfile.tsx` |
| `CrimeBreakdown` BOCSAR table with trend indicators | `frontend/src/components/report/CrimeBreakdown.tsx` |
| GIS facilities panel with real `<MapPanel>` in locator mode | `frontend/src/app/report/[suburb]/page.tsx` |
| `RedditQuote` 3-col grid | `frontend/src/components/report/RedditQuote.tsx` |
| `EvidenceTrace` horizontal pipeline | `frontend/src/components/report/EvidenceTrace.tsx` |

### Step 10 — Direction B (Comparator)

| Component | File |
|---|---|
| `app/report/compare/page.tsx` — route `?a=SuburbA&b=SuburbB` | `frontend/src/app/report/compare/page.tsx` |
| `CompareHeader` with verdict badge | same |
| `SplitLayout` — two `SuburbHero` columns | same |
| Center head-to-head dimension bars per `DIMENSIONS` | same |
| `SuburbAspects` — `AspectRadar` + `RedditQuote` per suburb | same |
| `RowsLayout` fallback (selectable via toggle) | same |
| `SuburbHero` with real `MapPanel` in locator mode | `frontend/src/components/report/SuburbHero.tsx` |
| Split-vs-rows layout toggle in header | `frontend/src/app/report/compare/page.tsx` |

### Additional Improvements Implemented

| # | Feature | Where |
|---|---|---|
| 1 | Out-of-scope empty state with suburb suggestion chips | `ChatBubbles.tsx` + `page.tsx` |
| 3 | Follow-up suggestion chips after each assistant response | `AssistantBubble` in `ChatBubbles.tsx` |
| 5 | Confidence dot per `<Cite>` footnote (🟢 ≥10 / 🟡 4–9 / 🔴 1–3 retrieved) | `Cite.tsx` |
| 6 | "Last updated" per source in EvidenceDrawer (BOCSAR 2024, ArcGIS live; Reddit red) | `EvidenceDrawer.tsx` |
| 7 | Grouped source badges with count (×n deduplication) in `AssistantBubble` sources strip | `ChatBubbles.tsx` |
| 8 | Skeleton loading states for score rail cards and AssistantBubble | `MapPanel.tsx`, `ChatBubbles.tsx` |
| 9 | Cancel query button with AbortController (3s delay before showing) | `ChatInput.tsx` + `page.tsx` |
| 10 | Map legend — dynamic gradient per layer | `MapPanel.tsx` |

---

## ⚠ Not Implemented / Red Placeholders

### Missing Backend API Fields (red placeholders rendered in UI)

The following fields are not yet returned by `/api/chat` and are rendered with a red `bg-red-500/20 border border-red-500` placeholder wherever they would appear:

| Field | Used in | Why missing |
|---|---|---|
| `router.categories` | `AssistantBubble` router chips row | Backend router output not exposed in API response. Fallback: defaults to `["sentiment"]` with `latencyMs: 0` |
| `router.latencyMs` | Router chips row timing label | Same as above |
| `claims[]` (segmented claims with citations) | `AssistantBubble` answer body with `<Cite>` footnotes | API returns `answer` as a plain string. Client-side fallback: splits by sentence into `Claim[]` with empty `cites[]` — citations and map highlight will not work until backend segments claims |
| `quality.evidence_trace_summary` (structured) | `EvidenceDrawer` pipeline rows, `EvidenceTrace` in Direction C | Currently returned as a plain string. Red placeholder shown when not structured. String form is displayed as-is as fallback |
| `suburb_scores` | Direction C executive summary, Direction B comparator heroes | New field; not yet in `/api/chat` response. Red placeholder in executive summary and comparator when absent |
| `aspect_scores` | Direction C aspect radar, Direction B aspect radar | DeBERTa-v3 ABSA per suburb; not yet returned |
| `emotion_profile` | Direction C emotion profile | GoEmotions distribution; not yet returned |
| `reddit_highlights` | Direction C reddit grid, Direction B reddit quotes | Not yet returned |
| `crime_breakdown` | Direction C crime table | BOCSAR per category; not yet returned |
| Reddit last crawl date | `EvidenceDrawer` source freshness row | Not available from API |

### Improvements Not Implemented

| # | Feature | Reason |
|---|---|---|
| 2 | Suburb disambiguation chip ("Did you mean Surry Hills?") | Requires NLP partial-match detection on the server side or a client-side suburb list fuzzy-match; out of scope for pure UI refactor |
| 4 | Score rail reacts to weighting sliders with delta badge | Requires structured `suburb_scores` from API, which is missing |
| 11 | Streaming visible pipeline (router chip appears first, then specialists) | Requires server-sent events or streaming response from `/api/chat`; current API is a single POST/response |
| 12 | "What's missing" section in Evidence Drawer | Requires structured specialist result metadata from API (which specialists returned no_data) |
| 13 | Permalink for reports with weights in URL (`?profile=safety:8,...`) | Low priority UX; not blocked technically but not implemented |
| 14 | 3-way comparator `CompareRows` auto-fallback | Direction B only; partial rows layout exists; 3-suburb detection not implemented |
| 15 | PDF upload CTA prominence | Upload CTA added to `ChatInput` footer as a visible button; full upload flow unchanged from original |

### Components Preserved Unchanged

- `OnboardingPanel` — onboarding flow untouched
- `AssistantSidebar` — file preserved (referenced by onboarding); not used in main 3-col layout
- `DetailedReportModal` — file preserved but not wired in new layout (replaced by `/report/[suburb]` route)
- `HexagonGrid`, `EmotionBars`, overview page — out of scope per README

---

*Sydney Liveability AI · ANLP AT2 · UTS MDSI Autumn 2026*
