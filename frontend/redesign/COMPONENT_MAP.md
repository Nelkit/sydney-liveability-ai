# Component Map

Maps each visual block in the redesign to the file you should create or modify in `frontend/src/`.

## New shared primitives (create these first)

Create under `frontend/src/components/ui/`:

| Reference (`source/primitives.jsx`) | New file | Notes |
|---|---|---|
| `CategoryChip` | `components/ui/CategoryChip.tsx` | Props: `kind: 'crime' \| 'gis' \| 'sentiment' \| 'comparator' \| 'out_of_scope'`, `active?`, `size?` |
| `SourceBadge` | `components/ui/SourceBadge.tsx` | Props: `kind: 'reddit' \| 'bocsar' \| 'arcgis' \| 'osm' \| 'tfnsw' \| 'pdf'`, `n?`, `onClick?` |
| `Cite` | `components/ui/Cite.tsx` | Inline `<sup>` footnote. Drives map polygon highlight via shared context |
| `ScoreGauge` | `components/ui/ScoreGauge.tsx` | Circular SVG gauge. Props: `value`, `size`, `label?` |
| `Bar`, `DivergingBar` | `components/ui/Bar.tsx` | Both small, can live in same file |
| `Pill` (Loved/Concern) | `components/ui/Pill.tsx` | Used in Direction C exec summary |
| `SectionCard` | `components/ui/SectionCard.tsx` | Title + hint header + body |

## Direction A — Chat experience

**Replaces:** the current `LiveabilityAssistant` sidebar + map layout.

| Reference component | Target file |
|---|---|
| `<DirectionA>` (top-level layout) | `app/(main)/page.tsx` or `components/liveability/ChatPanel.tsx` |
| `<UserBubble>`, `<AssistantBubble>` | `components/liveability/ChatBubbles.tsx` |
| `<ChatInput>` | `components/liveability/ChatInput.tsx` |
| `<MapHeader>`, `<ScoreRail>` | overlay inside `components/liveability/MapPanel.tsx` |
| `<EvidenceDrawer>`, `<PipelineRow>`, `<RetrievalBar>` | `components/liveability/EvidenceDrawer.tsx` (new) |

### `MapPanel.tsx` changes
- Add `layer: 'liveability' \| 'safety' \| 'transport' \| 'lifestyle'` prop and recolor polygons accordingly
- Add `activeSuburbs: string[]` prop (highlighted polygons)
- Add `hoveredSuburb` controlled prop and `onSuburbHover` callback
- Render `<MapHeader>` overlay (top) and `<ScoreRail>` overlay (bottom)
- Hide `data-screen-label` overlay names except for active suburbs to avoid the label collision issue seen in current screenshots

### Citation ↔ map hover sync
The cleanest pattern: a React Context `CitationHoverContext` providing `{ hoveredCite, setHoveredCite }`. `<Cite>` writes to it on mouseenter; `<MapPanel>` subscribes and highlights `hoveredCite.suburbs`.

## Direction B — Comparator split

**Replaces:** part of the `Detailed Report` route when the response contains 2 suburbs (or when query category includes `comparator`).

| Reference component | Target file |
|---|---|
| `<DirectionB>` | `app/report/compare/page.tsx` (new route) |
| `<CompareHeader>` | `components/report/CompareHeader.tsx` |
| `<SplitLayout>` | `components/report/CompareSplit.tsx` |
| `<RowsLayout>` | `components/report/CompareRows.tsx` |
| `<SuburbHero>` | `components/report/SuburbHero.tsx` (also reused in Direction C) |
| `<SuburbAspects>`, `<AspectRadar>` | `components/report/AspectRadar.tsx` |
| `<RedditQuote>` | `components/report/RedditQuote.tsx` |

The split-vs-rows tweak is optional in production. If you keep it, put it behind a user setting or query param `?layout=split|rows`.

## Direction C — Detailed Report (single suburb)

**Replaces:** the current `Detailed Report` page.

| Reference component | Target file |
|---|---|
| `<DirectionC>` | `app/report/[suburb]/page.tsx` |
| `<SectionCard>` | already created as primitive |
| `<AspectRadarFull>` | extend `components/report/AspectRadar.tsx` with a `size` variant |
| `<EmotionProfile>` | `components/report/EmotionProfile.tsx` |
| `<RedditQuoteFull>` | extend `components/report/RedditQuote.tsx` with a `variant: 'compact' \| 'full'` |
| `<EvidenceTrace>`, `<PipelineNode>`, `<RetrievalBar2>` | `components/report/EvidenceTrace.tsx` |

The crime breakdown and GIS facilities sections are inline in `<DirectionC>` — extract to `components/report/CrimeBreakdown.tsx` and `components/report/FacilitiesPanel.tsx` for cleanliness.

## API shapes used by the components

These are inferred from `source/data.jsx`. Map them to your existing FastAPI response or generate types from the OpenAPI schema.

```ts
type Suburb = {
  name: string;
  score: number;            // 0-100, weighted
  transport: number;
  safety: number;
  lifestyle: number;
  affordability: number;
  facilities: number;       // ArcGIS-derived
  walkability: number;      // OSM-derived
  crimeIdx: number;         // 0-1
  sentiment: number;        // 0-1, average ABSA
  cafes: number; restaurants: number; parks: number; playgrounds: number;
  sa4: string;
};

type AspectScore = {
  aspect: string;           // 'Nightlife' | 'Food & Cafe' | etc.
  pos: number;              // 0-1
  mentions: number;
};

type EmotionProfile = Record<
  'joy' | 'surprise' | 'neutral' | 'sadness' | 'fear' | 'anger' | 'disgust',
  number
>;

type RedditHighlight = {
  id: string;               // e.g. 't3_1abc23'
  q: string;                // quoted text
  aspect: string;
  sentiment: 'pos' | 'neu' | 'neg';
  up: number;
};

type CrimeRow = {
  cat: string;              // BOCSAR category
  v: number;                // per 100k
  trend: number;            // % YoY
};

type Citation = {
  n: number;                // footnote index
  src: 'reddit' | 'bocsar' | 'arcgis' | 'osm' | 'tfnsw' | 'pdf';
  suburbs: string[];        // for map highlight
  detail: string;           // hover/drawer copy
};

type AssistantMessage = {
  role: 'assistant';
  ts: string;
  router: {
    categories: ('crime' | 'gis' | 'sentiment' | 'comparator' | 'out_of_scope')[];
    suburbs: string[];
    latencyMs: number;
  };
  claims: { text: string; cites: Citation[] }[];
  summary?: { recommend: string; why: string };
};

type EvidenceTrace = {
  router: { ms: number; model: string; note: string };
  specialists: { id: string; ms: number; retrieved: number; store: string }[];
};
```

## Backend changes implied

The redesign expects a few additional fields from `/api/chat` that may not be in your current contract:

1. **Per-claim citation array** — answer must come pre-segmented into claims with their citations. Today it's likely a single string + a sources list. Either:
   - Restructure the response (cleaner but breaking change), or
   - Have a small client-side parser that splits on sentences and matches to source IDs (faster to ship)
2. **Router output exposed** — `quality.router = { categories, suburbs }` should be returned to the client (currently internal). Cheap to add.
3. **Latency per stage** — already present as `quality.evidence_trace_summary`; just need to expose timings per stage in a structured shape, not just a string.

Discuss with the backend team before shipping the redesign or you'll be blocked on these.

## Migration plan

1. **Sprint 1**: Tokens + primitives + new `MapPanel` props (no visible change yet, just plumbing)
2. **Sprint 2**: Direction A (the chat). Behind a feature flag.
3. **Sprint 3**: Direction C (single-suburb report). Replace existing `Detailed Report` directly.
4. **Sprint 4**: Direction B (comparator). New route. Wire from chat when 2 suburbs detected.
5. **Sprint 5**: Remove old components, flip feature flag, polish.
