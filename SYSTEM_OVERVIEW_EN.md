# Sydney Liveability AI — System Overview

> **Project:** ANLP 36118 · University of Technology Sydney (UTS)  
> **Program:** Master of Data Science and Innovation · Autumn 2026  
> **Team:** Ying-Kai Liao · Padmasri Srinivas · Nian-Ya Weng · Nelkit Chavez · Juan David Rodriguez · Luis Gerardo Robinson

---

## Table of Contents

1. [General Description](#1-general-description)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Backend](#4-backend)
   - [API Endpoints](#41-api-endpoints)
   - [Agent Pipeline](#42-agent-pipeline)
   - [Scoring Formula](#43-scoring-formula)
   - [Database](#44-database)
   - [ChromaDB (Vector Store)](#45-chromadb-vector-store)
5. [Frontend](#5-frontend)
   - [Pages and Components](#51-pages-and-components)
   - [Data Flow](#52-data-flow)
   - [Design System](#53-design-system)
6. [Data Sources and Ingestion](#6-data-sources-and-ingestion)
7. [Configuration and Environment Variables](#7-configuration-and-environment-variables)
8. [Architecture Decisions](#8-architecture-decisions)
9. [Known and Resolved Bugs](#9-known-and-resolved-bugs)
10. [System Strengths](#10-system-strengths)
11. [Limitations and Weaknesses](#11-limitations-and-weaknesses)
12. [Current Status by Area](#12-current-status-by-area)

---

## 1. General Description

Sydney Liveability AI is an AI-powered Sydney suburb recommendation web application. It combines structured government data (crime, transport, urban facilities), spatial data (PostGIS), community sentiment extracted from Reddit, and a multi-agent reasoning pipeline to answer natural language questions about where to live in Sydney.

The user defines a personalised weight profile (safety, transport, lifestyle, affordability, proximity to the CBD) through an onboarding conversation. The system ranks all available suburbs according to those weights, displays the top-5 on an interactive map, and allows the user to explore each suburb in depth via a chat grounded in cited evidence.

### Main user flow

```
Onboarding (weights chat)
    ↓
Profile ready → Map with top-5 suburbs coloured by liveability
    ↓
User types question → Multi-agent pipeline (router → specialists → synthesis)
    ↓
Response with markdown, cited sources, updated map
    ↓
Click on suburb → Detailed report (scores, crime, sentiment, Reddit)
```

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                    │
│                                                             │
│  OnboardingPanel → MapPanel → ChatPanel → EvidenceDrawer    │
│       ↑                ↑           ↑                        │
│   Weights         CivicData    StreamSSE                    │
└──────────┬─────────────┬───────────┬────────────────────────┘
           │             │           │
    POST /api/chat  GET /api/civic  GET /api/chat/stream
           │             │           │
┌──────────▼─────────────▼───────────▼────────────────────────┐
│                        BACKEND (FastAPI)                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Query Crew (CrewAI)                     │   │
│  │  Router → [Crime | Sentiment | GIS | Comparator]    │   │
│  │                    ↓                                 │   │
│  │             Synthesiser (LLM)                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │  PostgreSQL  │  │   ChromaDB   │  │  LLM Provider   │   │
│  │  (Supabase)  │  │  (Reddit)    │  │  (OpenRouter /  │   │
│  │  - suburbs   │  │  MiniLM-L6v2 │  │   Anthropic /   │   │
│  │  - bocsar    │  │  384-dim     │  │   OpenAI)       │   │
│  │  - sentiment │  └──────────────┘  └─────────────────┘   │
│  │  - osm       │                                           │
│  │  - transport │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

### Backend
| Technology | Version | Usage |
|-----------|---------|-------|
| Python | 3.12 | Production runtime (Render) |
| FastAPI | latest | HTTP framework, routing, validation |
| Uvicorn | latest | ASGI server |
| CrewAI | latest | AI agent orchestration |
| LangChain | latest | LLM abstraction, text splitting |
| LangChain Anthropic | latest | Claude integration |
| ChromaDB | latest | Vector store for Reddit embeddings |
| sentence-transformers | latest | MiniLM-L6-v2 embeddings (384-dim) |
| SQLAlchemy | 2.0+ | PostgreSQL ORM |
| psycopg2-binary | latest | PostgreSQL driver |
| GeoAlchemy2 | latest | PostGIS extension for SQLAlchemy |
| Pandas | latest | Data processing during ingestion |
| GeoPandas | latest | Geospatial data |
| Shapely | latest | Geometry (GeoPandas dependency) |
| Requests | latest | HTTP calls to external APIs |
| Transformers | latest | NLP models (HuggingFace) |
| Supabase (client) | latest | Reddit analysis cache |
| Pydantic-settings | latest | Typed configuration with .env |

### Frontend
| Technology | Version | Usage |
|-----------|---------|-------|
| Next.js | 14+ | React framework with App Router |
| React | 18+ | UI |
| TypeScript | 5+ | Static typing |
| Tailwind CSS | 3.x | Styling with custom OKLCH tokens |
| Framer Motion | latest | Animations and transitions |
| Leaflet.js | latest | Interactive map (dynamic import, SSR disabled) |
| Turf.js | latest | Client-side geospatial operations |
| react-markdown | 10+ | Markdown rendering in chat |
| remark-gfm | latest | GitHub Flavored Markdown |
| Lucide React | latest | Icons |
| next/font | built-in | Space Grotesk + JetBrains Mono |

### Infrastructure
| Service | Usage |
|---------|-------|
| Supabase | Hosted PostgreSQL + PostGIS, Session Pooler (port 5432) |
| Render | FastAPI backend hosting |
| Vercel | Next.js frontend hosting |
| OpenRouter | Default LLM provider (multi-model support) |

---

## 4. Backend

### 4.1 API Endpoints

#### `GET /`
Project metadata. Description, status, available endpoints.

#### `GET /health`
Health check. Returns `{"status": "ok"}`. Used by Render for liveness checks.

#### `GET /api/civic`
**Purpose:** Rank all suburbs by personalised liveability and return the top-5 as GeoJSON.

**Parameters (query, float 0.0–1.0):**
```
safety        (default: 0.25)
transport     (default: 0.25)
lifestyle     (default: 0.25)
affordability (default: 0.25)
nightlife     (default: 0.0)
proximity     (default: 0.0)
```
The sum of all weights must be ≈1.0 (tolerance ±0.001).

**Response:** GeoJSON `FeatureCollection` with 5 features. Each feature contains:
```json
{
  "type": "Feature",
  "properties": {
    "suburb": "Newtown",
    "liveability_score": 0.7823,
    "safety_score": 0.8100,
    "transport_score": 0.7500,
    "lifestyle_score": 0.7200,
    "nightlife_score": 0.6800,
    "proximity_score": 0.9100
  },
  "geometry": { "type": "MultiPolygon", ... }
}
```

**Caching:** In-memory cache with double-checked locking (`threading.Lock`). The first call loads all suburbs from the DB; subsequent calls apply weights in pure Python without touching the DB.

**Retry logic:** 3 attempts with exponential backoff (0.15s → 0.30s → 0.60s) on `OperationalError`.

**Errors:** HTTP 400 if weights don't sum to 1.0. HTTP 503 if DB fails after 3 attempts.

---

#### `POST /api/chat`
**Purpose:** Execute the multi-agent pipeline and return the complete response.

**Request body:**
```json
{
  "question": "Is Newtown safe at night?",
  "message": null,
  "weights": { "safety": 0.4, "transport": 0.3, "lifestyle": 0.2, "affordability": 0.1 }
}
```

**Response shape (complete):**
```json
{
  "answer": "string (markdown)",
  "sources": [{"source": "reddit|bocsar|arcgis|osm|tfnsw|pdf", "suburb": "..."}],
  "suburb_scores": [{"suburb": "...", "score": 0.78, "transport": ..., "safety": ...}],
  "map_state": {"activeSuburbs": ["Newtown"], "layer": "Safety", "heatmap_weights": {...}},
  "router": {"suburbs": [...], "categories": [...]},
  "quality": {"evidence_trace_summary": {...}},
  "claims": [{"text": "...", "cites": [1, 2]}],
  "aspect_scores": [{"aspect": "safety", "pos": 0.8, "mentions": 42}],
  "emotion_profile": {"joy": 0.3, "sadness": 0.1, ...},
  "reddit_highlights": [{"id": "...", "q": "...", "aspect": "...", "sentiment": "pos", "up": 120}],
  "crime_breakdown": [{"cat": "Assault", "v": 45, "trend": "improving"}]
}
```

---

#### `POST /api/chat/stream`
**Purpose:** SSE (Server-Sent Events) version of `/api/chat`. Emits real-time progress.

**Event format:**
```
event: step
data: {"text": "Analyzing crime data for Newtown..."}

event: done
data: { ...full ChatAPIResponse... }
```

**Headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`

---

#### `GET /api/reddit/{suburb}`
**Purpose:** Reddit sentiment profile for a specific suburb.  
**Cache:** Supabase `reddit_analyses` table with 24-hour TTL.  
**Response:** Sentiment aspects, emotions, narrative, sources.

---

### 4.2 Agent Pipeline

The pipeline uses CrewAI with sequential process. The central orchestrator is `backend/crews/query_crew.py`.

```
Question + Weights
      ↓
  ┌──────────┐
  │  Router  │  ← Deterministic, no LLM, zero cost
  └────┬─────┘
       │ categories: [crime, sentiment, gis, comparator, out_of_scope]
       │ suburbs_mentioned: [...]
       ▼
  ┌────────────────────────────────────────────┐
  │     Specialists (parallel where possible)   │
  │                                            │
  │  [Crime]  [Sentiment]  [GIS]  [Comparator] │
  └────────────────────────┬───────────────────┘
                           ↓
                   ┌──────────────┐
                   │  Synthesiser │  ← LLM (scenario-aware prompt)
                   └──────────────┘
                           ↓
                    Response payload
```

#### Agent: Router
- **Logic:** Deterministic regex + keywords (no LLM).
- **Suburb detection:** Case-insensitive regex over DB list, sorted by length (longest first to avoid conflicts).
- **Categories:**
  - `crime` ← keywords: "safe", "crime", "dangerous", "robbery", "assault"
  - `sentiment` ← keywords: "feel", "vibe", "community", "residents", "opinion"
  - `gis` ← keywords: "park", "transport", "facilities", "cafe", "walk", "amenities"
  - `comparator` ← keywords: "vs", "versus", "compare", "difference", "better"
  - `out_of_scope` ← no suburbs + default categories → redirects the user
- **Default:** ["sentiment", "gis"] if no specific keywords.

#### Agent: Crime
- **Data:** PostgreSQL `bocsar` table.
- **Key output:** `crime_summary` (type → total), `trend` ("improving"/"worsening"/"insufficient data"), `sa4_area`.
- **Trend:** Compares most recent year vs. prior year (total sum of incidents).

#### Agent: Sentiment (Agentic RAG — A-RAG)
- **Owner:** Ying-Kai Liao
- **Type:** Fully agentic; the LLM controls the strategy iteratively.
- **Tools available to the LLM:**
  - `get_suburb_aspect(suburb, dimension)` → cached score or "no_data"
  - `search_posts(suburb, query, dimension, k)` → ChromaDB semantic search
- **8 analysis dimensions:** safety, food_and_cafe, nightlife, affordability, transport, community, noise, green_space
- **Thresholds:** positive ≥ 0.65 · negative ≤ 0.45 · neutral: 0.45–0.65
- **Evidence trace:** side-channel via `contextvars`; records each tool call with step, args, result_count, preview, elapsed_ms.

#### Agent: GIS
- **Owners:** Nelkit Chavez, Luis Robinson, Padmasri Srinivas
- **Data:** PostgreSQL tables `suburbs`, `osm_scores`, `transport_scores`.
- **Composite score:**
  ```
  combined_score = (facilities_score * 0.35) + (osm_score * 0.35) + (transport_score * 0.30)
  ```
- **Output:** Detailed facilities, OSM amenities, transport data, combined_score.

#### Agent: Comparator
- **Owners:** Padmasri Srinivas, Luis Robinson
- **Input:** suburb_a, suburb_b, categories
- **Winner logic:**
  - GIS: higher `combined_score` wins
  - Crime: lower severity wins
  - Sentiment: higher overall score wins

#### Agent: Synthesiser
- **Owner:** Nelkit Chavez
- **Scenario-aware prompts (3 scenarios):**

  **`out_of_scope`:** Hardcoded response with examples of valid questions in markdown.

  **`single` (1 suburb):**
  ```
  - 1 sentence on the suburb's general character
  - **bold** for 1-2 key metrics
  - List of 2-3 highlights/concerns
  - Closing with invitation to the detailed report (blockquote >)
  ```

  **`comparator` (2+ suburbs):**
  ```
  - 1 sentence declaring which "wins" or that they suit different lifestyles
  - **bold** for the main differentiator
  - 1-line list per suburb with its strongest point
  - Invitation to the Compare view (blockquote >)
  ```

- **Sources:** Iterates all agent outputs to build the source list; adds default badge per agent if it ran but returned no explicit sources.
- **Debug modes** (env `SYNTHESIS_DEBUG_MODE`): `off` (default) · `gis` · `all`
- **RAG:** Retrieves ChromaDB chunks filtered by suburb before calling the LLM.

---

### 4.3 Scoring Formula

**File:** `backend/core/scoring.py`

#### Final liveability score

```
liveability = (safety        × w_safety)
            + (transport     × w_transport)
            + (lifestyle     × w_lifestyle)
            + (affordability × w_affordability)
            + (nightlife     × w_nightlife)
            + (proximity     × w_proximity)
```

All components are normalised to [0.0, 1.0].  
Default weights: safety=0.25, transport=0.25, lifestyle=0.25, affordability=0.25, nightlife=0.0, proximity=0.0.

#### Individual components

| Dimension | Source | Calculation |
|-----------|--------|-------------|
| **Safety** | `bocsar` (most recent year) | Inverse-normalised: `1 - (crime / max_crime)` across all suburbs |
| **Transport** | `gis_combined` | `transport×0.50 + walkability×0.20 + facilities×0.15 + osm×0.15` |
| **Lifestyle** | `sentiment_scores` aspect "community" | Fallback: → "lifestyle" → `facilities_score` |
| **Affordability** | `sentiment_scores` aspect "affordability" | Fallback: → 0.5 |
| **Nightlife** | `sentiment_scores` aspect "nightlife" | Fallback: → "community" → `facilities_score` |
| **Proximity** | PostGIS `ST_Distance` centroid → CBD | `1 - (dist_m / 35000)` clamped [0,1] |

**CBD:** lat=-33.8688, lng=151.2093. `MAX_DIST_M=35000` metres.

#### Normalisation function
```python
def _clamp_unit(value):
    if value is None: return 0.0
    if value > 1.0: value /= 100.0  # scores on 0-100 scale
    return max(0.0, min(1.0, value))
```

#### Thread-safe caching
```python
_RAW_CACHE: dict | None = None
_CACHE_LOCK = threading.Lock()

# Double-checked locking:
if _RAW_CACHE is None:
    with _CACHE_LOCK:
        if _RAW_CACHE is None:
            _RAW_CACHE = _load_raw(None)
```
First call: loads all DB data (6 tables in one session). Subsequent calls: apply weights in pure Python — **no DB**.

---

### 4.4 Database

**ORM:** SQLAlchemy 2.0+  
**DB:** PostgreSQL with PostGIS extension  
**Hosting:** Supabase (Session Pooler, port 5432)

#### Table: `suburbs`
| Column | Type | Description |
|--------|------|-------------|
| `sal_code` | str PK | SAL code (Statistical Area Level) |
| `suburb` | str | Suburb name |
| `car_share_bays_count` | int? | Car-sharing bays |
| `libraries_count` | int? | Libraries |
| `mobility_parking_count` | int? | Mobility-impaired parking |
| `sports_facilities_count` | int? | Sports facilities |
| `total_facilities` | int? | Total facilities |
| `facilities_score` | float? | Normalised facilities score |
| `walkability_score` | float? | Walkability score |
| `geometry` | PostGIS MultiPolygon(4326)? | Suburb polygon geometry |

#### Table: `bocsar`
| Column | Type | Description |
|--------|------|-------------|
| `id` | int PK autoincrement | |
| `suburb` | str | Suburb name |
| `crime_type` | str | Offence type |
| `year` | int | Year |
| `incident_count` | int | Number of incidents |
| `sa4_area` | str | SA4 area (statistical region) |

#### Table: `sentiment_scores`
| Column | Type | Description |
|--------|------|-------------|
| `suburb` | str PK | |
| `aspect` | str PK | Liveability dimension (8 aspects) |
| `score` | float? | Score 0-1 |
| `mentions` | int? | Number of mentions |
| `confidence` | float? | Model confidence |
| `coverage` | str? | Data coverage |
| `source` | str? | Source |

#### Table: `emotion_profiles`
| Column | Type | Description |
|--------|------|-------------|
| `suburb` | str PK | |
| `joy`, `surprise`, `neutral`, `sadness`, `anger`, `fear`, `disgust` | float? | 7 emotions |
| `post_count` | int? | Posts analysed |
| `fetched_at` | datetime? | Analysis date |
| `confidence` | float? | |
| `confidence_tier` | str? | "high"/"medium"/"low" |

#### Table: `suburb_narratives`
| Column | Type | Description |
|--------|------|-------------|
| `suburb` | str PK | |
| `narrative` | Text? | Generated narrative summary |
| `sources` | JSON? | List of sources used |

#### Table: `osm_scores`
| Column | Type | Description |
|--------|------|-------------|
| `suburb` | str PK | |
| `osm_score` | float? | Composite OSM score |
| `cafe`, `restaurant`, `gym`, `school`, `hospital`, `pharmacy`, `library`, `park`, `playground`, `sports_centre` | int? | Count per amenity type |

#### Table: `transport_scores`
| Column | Type | Description |
|--------|------|-------------|
| `suburb` | str PK | |
| `bus_stops` | int? | |
| `train_stations` | int? | |
| `light_rail_stops` | int? | |
| `bike_paths_km` | float? | |
| `avg_commute_min` | float? | Average commute in minutes |
| `transport_score` | float? | Normalised score |
| `avg_services_per_hour` | float? | Average service frequency |
| `stop_count` | int? | Total stops |
| `source` | str? | |

#### Connection pool configuration
```python
engine = create_engine(
    DATABASE_URL,            # sslmode=require enforced
    use_native_hstore=False, # prevents hstore_oids query on Supabase Transaction Pooler
    pool_size=3,             # max 3 permanent connections
    max_overflow=2,          # +2 temporary = 5 total (well below Supabase's limit of 15)
    pool_timeout=10,
    pool_recycle=55,         # recycle before Supabase timeout (60s)
    pool_pre_ping=True,
)
```

**Critical note:** Supabase's Session Pooler (port 5432) has a limit of 15 connections. The Transaction Pooler (port 6543) is incompatible with psycopg2 because it runs `hstore_oids` during the connection and Supabase closes the SSL during that query.

---

### 4.5 ChromaDB (Vector Store)

**Collection:** `sydney_liveability`  
**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, cosine similarity)  
**Path:** `./data/chromadb/` (relative to repo root, not CWD)  
**Snapshot size:** ~156 MB

#### Chunking strategy
- **Splitter:** `RecursiveCharacterTextSplitter`
- **Chunk size:** 200 characters
- **Overlap:** 20 characters
- **Filter:** Empty chunks removed

#### Required metadata per chunk
```python
{
    "suburb": str,       # Title Case with spaces (e.g., "Surry Hills")
    "source": str,       # "reddit_post" | "reddit_comment" | "sentiment_narrative" | "sentiment_quote"
    "dimension": str,    # "safety" | "community" | "food_and_cafe" | "nightlife" | ...
    "chunk_index": int,  # Sequence within the post/narrative
}
```

#### Deterministic IDs
```
{source}-{suburb_slug}-{post_id_or_hash}-{chunk_index}
# Example: reddit_post-newtown-abc123def456-0
```
Enables re-ingestion without duplicates (upsert in place).

#### Retrieval function
```python
query_chunks(query, k=5, filters={"suburb": "Newtown", "dimension": "safety"})
# Returns: [{"text": str, "metadata": dict, "distance": float}]
```

---

## 5. Frontend

### 5.1 Pages and Components

#### Main page: `/` (`frontend/src/app/page.tsx`)

**Layout:** 3-column grid (`grid-cols-[440px_1fr_320px]`)
- **Col 1:** Chat sidebar (messages + input)
- **Col 2:** MapPanel (Leaflet, dynamically imported without SSR)
- **Col 3:** EvidenceDrawer (collapsible)

**Main state:**
```typescript
isHydrated: boolean          // localStorage loaded
isAppOpen: boolean           // onboarding completed
profileReady: boolean        // 5 weights selected
weights: Weights             // {transport, safety, lifestyle, afford, proximity}
selectedLevels: Partial<Record<keyof Weights, ImportanceLevelKey>>
civicData: CivicResponse | null
onboardingMessages: ChatMessage[]
displayMessages: StreamMessage[]
```

**Storage keys:**
- `sydney-liveability-preferences-v1` → weights and profile state
- `user_weights` → normalised weights for the backend

---

#### Main components

| Component | File | Purpose |
|-----------|------|---------|
| `OnboardingPanel` | `liveability/OnboardingPanel.tsx` | Landing + conversational weight profile. 3 phases: hero / weights chat / profile ready. |
| `MapPanel` | `liveability/MapPanel.tsx` | Leaflet map with polygons, dimension heatmap, click → chat, flyToBounds on top-5. |
| `AssistantBubble` | `liveability/ChatBubbles.tsx` | AI response bubble with word-by-word streaming, ReactMarkdown on completion, action chips. |
| `UserBubble` | `liveability/ChatBubbles.tsx` | User message bubble. |
| `ChatInput` | `liveability/ChatInput.tsx` | Text input + category-coded suggestion chips + source footer. |
| `EvidenceDrawer` | `liveability/EvidenceDrawer.tsx` | Side panel with pipeline trace, active citations, retrieval breakdown, source freshness. |
| `ReportModal` | `liveability/ReportModal.tsx` | Full report modal (individual or comparative). Renders ReactMarkdown + strips trailing blockquote CTA. |
| `ImportanceSlider` | `liveability/ImportanceSlider.tsx` | 1–10 slider with local state; commits only on mouseUp/touchEnd (not on drag). |
| `SharedBrand` | `liveability/SharedBrand.tsx` | Logo with `layoutId` for Framer Motion transition onboarding → app. |
| `SuburbHero` | `report/SuburbHero.tsx` | Suburb report header with scores and ranking badge. |
| `AspectRadar` | `report/AspectRadar.tsx` | 8-dimension sentiment radar chart. |
| `EmotionBars` | `report/EmotionBars.tsx` | 7-emotion bars (joy, sadness, fear, anger, surprise, neutral, disgust). |
| `RedditQuote` | `report/RedditQuote.tsx` | Reddit highlight with corrected link (no double-prefix URL). |
| `CrimeBreakdown` | `report/CrimeBreakdown.tsx` | Crime table by category with trend indicator. |
| `EvidenceTrace` | `report/EvidenceTrace.tsx` | Horizontal pipeline visualisation in the report. |
| `SourceBadge` | `ui/SourceBadge.tsx` | Source badge: reddit · bocsar · arcgis · osm · tfnsw · pdf. |
| `Bar` | `ui/Bar.tsx` | Generic progress bar. |
| `ScoreGauge` | `ui/ScoreGauge.tsx` | Circular score gauge. |

---

#### Other pages

**`/report/[suburb]`** (`frontend/src/app/report/[suburb]/page.tsx`)  
Complete report for a suburb. Shows: SuburbHero, AspectRadar, EmotionBars, RedditQuote highlights, CrimeBreakdown, EvidenceTrace.

**`/report/compare`** (`frontend/src/app/report/compare/page.tsx`)  
Side-by-side comparison of two suburbs. Params: `?a=Newtown&b=Glebe`.

---

### 5.2 Data Flow

#### Onboarding → Map

```
1. User completes 5 sliders (transport, safety, lifestyle, affordability, proximity)
2. profileReady = true → setIsAppOpen(true) via openAppFromOnboarding()
3. useEffect [isHydrated, profileReady, selectedLevels] fires the fetch:
   GET /api/civic?transport=0.25&safety=0.3&...
   ← Only called when profileReady=true (not during onboarding)
4. civicData → rankedSuburbs (top-5) → MapPanel receives ranked[]
5. MapPanel flyToBounds to top-5 on data arrival (hasFittedBoundsRef guard)
```

#### Chat with streaming

```
1. User types question → POST /api/chat/stream
2. EventSource receives events:
   - "step": updates progress text in bubble
   - "done": full payload → AssistantBubble updates
3. During streaming: word-by-word text with animated cursor
4. On completion (isDone=true): ReactMarkdown renders the full answer
5. map_state.activeSuburbs → MapPanel flyToBounds to mentioned suburbs
6. sources → SourceBadge badges in the bubble
7. suburb_scores → scores sidebar
```

#### Markdown response normalisation

The LLM may return `\n` literal (backslash + n) instead of real line breaks. The frontend normalises before passing to ReactMarkdown:
```typescript
const normalized = fullText.replace(/\\n/g, "\n");
```

The ReportModal also strips the trailing blockquote CTA that the LLM appends for the chat (not needed in the report):
```typescript
const answer = rawAnswer.replace(/\n>\s+[^\n]*$/s, "").trimEnd();
```

---

### 5.3 Design System

**Tokens:** OKLCH custom in `tailwind.config.ts`. In Tailwind 3.x, OKLCH is written as raw CSS values (Tailwind 3 has no native support without a plugin).

**Semantic colours:**
```
bg-bg         → Base background
bg-bg-elev    → Elevated background (cards, popovers)
text-fg       → Primary text
text-fg-muted → Secondary text
border-border → Borders
accent        → Accent colour (indigo)
```

**Shadows:**
```
shadow-float   → Soft shadow for cards
shadow-floatLg → Large shadow for modals and CTAs
```

**Typography:**
- Body: Space Grotesk
- Monospace: JetBrains Mono (evidence trails, badges, code)

**Onboarding background:**
```css
radial-gradient(circle at 30% 18%, rgba(254,215,170,0.22), transparent 28%),
linear-gradient(180deg, #eff2f8, #e9edf6)
```

---

## 6. Data Sources and Ingestion

### BOCSAR (Crime Statistics)
- **Source:** Bureau of Crime Statistics and Research NSW
- **Dataset:** 2024
- **Scripts:** `data_extraction/process_bocsar.py` → `backend/scripts/ingest_bocsar.py`
- **Format:** CSV (suburb, crime_type, year, incident_count, sa4_area)
- **Target table:** `bocsar`

### ArcGIS / City of Sydney
- **Source:** City of Sydney ArcGIS REST API
- **Dataset:** 2026
- **Scripts:** `data_extraction/extract_arcgis.py` → `backend/scripts/ingest_arcgis.py`
- **Data:** Facilities (libraries, car-share, mobility parking, sports), walkability score
- **Geometry:** `data/processed/suburbs.geojson` (committed, static NSW suburb polygons)
- **Target table:** `suburbs` + PostGIS geometry

### OpenStreetMap (OSM)
- **Source:** OSM via Overpass API / OSMNX
- **Dataset:** 2026
- **Scripts:** `data_extraction/extract_osm.py` → `backend/scripts/ingest_osm.py`
- **Amenities:** cafe, restaurant, gym, school, hospital, pharmacy, library, park, playground, sports_centre
- **Target table:** `osm_scores`

### Reddit r/sydney
- **Source:** Reddit API via PRAW
- **Volume:** 20k+ posts and comments
- **Scripts:** `data_extraction/extract_reddit.py`
- **Processing pipeline:**
  1. Raw extraction via PRAW
  2. NLP cleaning and preprocessing
  3. Sentiment analysis by dimension (8 aspects, HuggingFace model)
  4. Emotion profiles (7 emotions, Transformers model)
  5. Summarised narrative generation
  6. PostgreSQL ingestion: `sentiment_scores`, `emotion_profiles`, `suburb_narratives`
  7. Embedding + upsert to ChromaDB (MiniLM-L6-v2)
- **ChromaDB index build time:** ~10 hours (prebuilt snapshot available on GitHub Releases)
- **Production cache:** Supabase `reddit_analyses` table with 24-hour TTL

### GTFS / Transport NSW
- **Source:** TfNSW GTFS feeds + OSM transit data
- **Dataset:** 2026
- **Scripts:** `data_extraction/extract_transport.py` → `backend/scripts/ingest_transport.py`
- **Data:** bus_stops, train_stations, light_rail_stops, bike_paths_km, avg_commute_min, transport_score, avg_services_per_hour
- **Target table:** `transport_scores`

### PDF Community Reports
- **Source:** City of Sydney community snapshots (PDF)
- **Scripts:** `data_extraction/parse_pdf.py`, `parse_pdf_quick_insights.py`, `parse_community_report_stats.py`
- **Ingestion:** `backend/scripts/ingest_pdf.py`
- **Content:** Demographic, economic, and housing data

---

## 7. Configuration and Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---------|---------|-------------|
| `LLM_PROVIDER` | `openrouter` | `openrouter` · `anthropic` · `openai` |
| `LLM_MODEL` | `nvidia/nemotron-3-super-120b-a12b:free` | Base model for all agents |
| `LLM_AGENT_MODELS_JSON` | — | JSON map `{"router": "model-x", "synthesiser": "claude-3-5-sonnet"}` for per-agent override |
| `OPENROUTER_API_KEY` | — | Required if `LLM_PROVIDER=openrouter` |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `DATABASE_URL` | — | `postgresql://user:pass@host:5432/db` (use port 5432, not 6543) |
| `CHROMADB_PATH` | `./data/chromadb` | Absolute or relative path to repo root |
| `FRONTEND_URL` | `http://localhost:3000` | Origin for CORS |
| `SYNTHESIS_DEBUG_MODE` | `off` | `off` · `gis` · `all` |
| `WALKSCORE_API_KEY` | — | For WalkScore ingestion (not production) |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Backend base URL |
| `NEXT_PUBLIC_APP_VERSION` | read from `package.json` via `next.config.js` | Version shown in UI |

---

## 8. Architecture Decisions

### Scoring in backend, not frontend
Liveability scores are calculated in the backend (`core/scoring.py`) as the single source of truth, used by both `/api/civic` and the synthesiser agent. The frontend has static scores in `data.ts` only as a visual fallback when the backend hasn't responded.

### In-memory cache with double-checked locking
The first call to `/api/civic` loads all DB data into `_RAW_CACHE`. Subsequent calls apply weights in pure Python. The lock prevents concurrent requests (especially during onboarding where the frontend used to fire 5 requests) from exhausting the Supabase connection pool.

### Civic fetch only when profileReady
The frontend doesn't call `/api/civic` during onboarding. The useEffect has a `!profileReady` guard. This prevents 5 concurrent requests (one per slider during onboarding) that caused `EMAXCONNSESSION` on the Supabase Session Pooler (limit: 15 connections).

### `use_native_hstore=False`
SQLAlchemy + psycopg2 runs an `hstore_oids` introspection query on connect. Supabase closes the SSL connection during that query on the Transaction Pooler (port 6543). The fix is `use_native_hstore=False` in `create_engine` and using the Session Pooler (port 5432).

### Markdown in chat: streaming → ReactMarkdown
During streaming: word-by-word text with animated cursor (split by `/\s+/` to preserve line breaks). On completion (`isDone`): the original full text is passed to `ReactMarkdown` with `remark-gfm`. This avoids layout flash during the stream and guarantees correct rendering on finish.

### Scenario-aware prompts
The synthesiser detects 3 scenarios (`single`, `comparator`, `out_of_scope`) and uses distinct prompts. This produces shorter, more structured, and more actionable responses than a single generic prompt. The LLM is instructed to end with a blockquote `>` inviting to the dashboard (which the ReportModal strips).

### LLM-free router
The router is entirely deterministic (regex + keywords). This keeps latency low in the routing step and reduces LLM costs. The tradeoff is less flexibility for ambiguous questions.

### 3-column main layout
Chat (440px fixed) + Map (flex) + Evidence (320px collapsible). The evidence panel can be hidden. The map is dynamically imported with `{ ssr: false }` to avoid `window` errors during Next.js SSR.

---

## 9. Known and Resolved Bugs

| Bug | Root Cause | Fix | Files |
|-----|-----------|-----|-------|
| `EMAXCONNSESSION` on Supabase | 5 concurrent requests during onboarding + pool_size too large | Fetch only when `profileReady=true` + pool reduced to 3+2 + threading.Lock in cache | `page.tsx`, `scoring.py`, `postgres.py` |
| SSL `hstore_oids` on Transaction Pooler | psycopg2 runs SSL introspection incompatible with port 6543 | `use_native_hstore=False` + use port 5432 | `postgres.py` |
| Markdown not rendering in chat | `split(" ")` didn't split `\n` + reconstructed `streamedText` lost newlines | `split(/\s+/)` + use original `fullText` in `isDone` + normalise `\\n` → `\n` | `ChatBubbles.tsx` |
| Markdown not rendering in ReportModal | Used `dangerouslySetInnerHTML` for raw markdown text | Replaced with `ReactMarkdown` with `flex flex-col` wrapper | `ReportModal.tsx` |
| Reddit links double-prefix | `href=https://reddit.com/comments/${q.id}` where `q.id` was already a full URL | `q.id.startsWith("http") ? q.id : ...` | `RedditQuote.tsx` |
| Sources strip only showed Reddit | Synthesiser only read `outputs["sentiment"]` for sources | Iterates all agents; adds default badge per agent if it ran | `synthesiser.py` |
| Slider fires on every drag | `onChange` called parent on every movement | Local `dragging` state; commit only on `mouseUp`/`touchEnd`/`keyUp` | `ImportanceSlider.tsx` |
| Top-5 map zoom doesn't occur when navigating from onboarding | `hasFittedBoundsRef` was set to `true` with `ranked=[]` before data arrived; `isLoading` never transitioned `true→false` on that mount | New `useEffect` that resets the guard when `ranked.length` goes from `0→N` | `MapPanel.tsx` |
| Profile panel shown on refresh | The `isAppOpen` `useEffect` fired `setProfileOpen(true)` for both onboarding and localStorage hydration | `openAppFromOnboarding()` function only called from the onboarding CTA; hydration uses `setIsAppOpen` directly | `page.tsx` |
| `geoalchemy2` missing in production | Not in `requirements.server.txt` | Added | `requirements.server.txt` |
| Back button in onboarding in wrong position | Was in the header | Moved to "Profile progress" card, same row | `OnboardingPanel.tsx` |

---

## 10. System Strengths

### Real multi-agent pipeline
This is not a single LLM answering general questions. The system has specialised agents with their own tools (SQL queries, ChromaDB search), each with a bounded responsibility. The router decides which agents run, reducing LLM costs and increasing precision.

### Auditable evidence
Every response includes a pipeline trace: which agents ran, how many chunks were retrieved, latency per specialist. The user can see exactly where each claim came from.

### Multi-source grounding
Responses combine quantitative data (crime counts, transport scores, OSM amenity counts) with qualitative sentiment (20k+ Reddit posts embedded and retrieved by semantic relevance). This produces richer answers than any single source alone.

### Customisable scoring
The user defines their own weights for 5 dimensions. The map and ranking are recalculated instantly (in Python, without a DB call thanks to the cache).

### Efficient cache architecture
The in-memory cache avoids hitting Supabase on every weight change. Suburb scores are pre-computed once; only weight algebra is applied on subsequent requests.

### Real streaming
The chat uses SSE to show real-time progress (which agent is running, which data is being retrieved) before returning the final response. This dramatically improves the perceived latency experience.

### Coherent design system
OKLCH tokens, consistent typography (Space Grotesk + JetBrains Mono), semantic shadows, and a colour system by source category. The UI scales without inconsistencies.

---

## 11. Limitations and Weaknesses

### Static data (no automatic updates)
The Reddit datasets (embeddings), BOCSAR, OSM, and GTFS are snapshots from 2024/2026. There is no automatic update pipeline. The ChromaDB index takes ~10 hours to rebuild from scratch.

### Supabase connection limit
Supabase's free/basic plan has a limit of 15 connections on the Session Pooler. The pool is configured at the minimum viable setting (3+2). Under high concurrent load (multiple simultaneous users), the `/api/civic` endpoint may return 503 if the cache is not warm.

### Fragile deterministic router
The router uses regex and keywords. Ambiguous questions or unexpected vocabulary may not be classified correctly. Example: "How quiet is Glebe?" might not trigger `crime` because "quiet" is not in the keyword set.

### Uneven suburb coverage on Reddit
Popular suburbs (Newtown, Glebe, Surry Hills) have many chunks in ChromaDB; peripheral suburbs have few or none. The sentiment of suburbs with little coverage defaults to `0.5` (neutral).

### Sentiment scores not updated dynamically
Sentiment scores in PostgreSQL are pre-computed. If a suburb's sentiment changes (new development, event, etc.), it is not reflected until a manual re-ingestion.

### No authentication
There is no user system or authentication. Weights are stored in `localStorage`. In public production, all users share the same backend.

### Variable pipeline latency
The multi-agent pipeline can take 5–15 seconds depending on the configured LLM model and question complexity. Streaming mitigates perception, but real latency is high.

### Single LLM provider dependency
Although the configuration supports OpenRouter/Anthropic/OpenAI, a single default model is used in production. There is no automatic fallback if the provider fails.

---

## 12. Current Status by Area

| Area | Status | Notes |
|------|--------|-------|
| API `/api/civic` | ✅ Functional | With cache and retry logic |
| API `/api/chat/stream` | ✅ Functional | Full SSE streaming |
| Router agent | ✅ Functional | Deterministic, no LLM |
| Crime agent | ✅ Functional | BOCSAR 2024 |
| Sentiment agent (A-RAG) | ✅ Functional | ChromaDB + PostgreSQL |
| GIS agent | ✅ Functional | OSM + ArcGIS + GTFS |
| Comparator agent | ✅ Functional | 2 suburbs, 3 dimensions |
| Synthesiser | ✅ Functional | Scenario-aware, markdown |
| Interactive map | ✅ Functional | Leaflet, heatmap, flyToBounds |
| Chat streaming frontend | ✅ Functional | Word-by-word + ReactMarkdown |
| Onboarding | ✅ Functional | 5 weights, back button, scroll sections |
| ReportModal (individual) | ✅ Functional | Markdown rendered |
| ReportModal (compare) | ✅ Functional | Side-by-side |
| EvidenceDrawer | ✅ Functional | Pipeline trace, source freshness |
| Landing below-the-fold | ✅ Functional | About, sources, dev info, disclaimer |
| CBD Proximity scoring | ✅ Implemented | PostGIS ST_Distance from centroid |
| Reddit router endpoint | ✅ Functional | With Supabase cache |
| Data ingestion | ✅ Complete | Scripts in `data_extraction/` and `backend/scripts/` |
| Automatic data updates | ❌ Not implemented | Manual re-ingestion required |
| User authentication | ❌ Not implemented | localStorage only |
| Automated tests | ⚠️ Partial | Tests in `backend/tests/`, limited coverage |

---

*Document generated on 2026-05-03. To update, modify this file or regenerate by reading the codebase.*
