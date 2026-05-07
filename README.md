# Sydney Liveability AI
[![Frontend: Next.js](https://img.shields.io/badge/Frontend-Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vector Store: ChromaDB](https://img.shields.io/badge/VectorStore-ChromaDB-FF6F00?style=flat)](https://www.trychroma.com/)
[![RAG: LangChain](https://img.shields.io/badge/RAG-LangChain-121212?style=flat)](https://langchain.com/)
[![Agents: CrewAI](https://img.shields.io/badge/Agents-CrewAI-6366f1?style=flat)](https://www.crewai.com/)
[![DB: PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

An AI-powered suburb recommendation platform for Greater Sydney. Combines structured government data (crime, transport, urban facilities), geospatial data (PostGIS), and community sentiment extracted from Reddit r/sydney to answer natural-language questions about where to live — backed by a multi-agent RAG pipeline with auditable evidence traces.

---

## Table of Contents

- [Overview](#-overview)
- [System Architecture](#️-system-architecture)
- [Local Setup](#-local-setup)
- [Environment Variables](#-environment-variables)
- [RAG Evaluation Harness](#-rag-evaluation-harness)
- [Data Sources](#️-data-sources)
- [NLP Pipeline and Models](#-nlp-pipeline-and-models)
- [Ingestion Pipeline](#-ingestion-pipeline)
- [Known Limitations](#️-known-limitations)
- [Team](#-team)
- [Links](#-links)

---

## 🧭 Overview

- **Subject:** ANLP 36118, Master of Data Science and Innovation, University of Technology Sydney (UTS), Autumn 2026
- **Assessment:** AT2B — NLP system with multi-agent pipeline, RAG, and a production web interface
- **Scope:** Suburb-level liveability analysis for Greater Sydney using crime statistics, transport data, OSM amenities, and community sentiment extracted from Reddit r/sydney
- **Live demo:** [sydney-liveability-ai.vercel.app](https://sydney-liveability-ai.vercel.app)
- **Architecture diagram:** [reports/AppendixA - system_architecture.png](reports/AppendixA%20-%20system_architecture.png)

The user defines a personalised weight profile (safety, transport, lifestyle, affordability, proximity to CBD) through a conversational onboarding flow. The system ranks all available suburbs, displays the top-5 on an interactive map, and allows the user to explore each suburb in depth via a chat grounded in cited evidence.

---

## 🏗️ System Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                     FRONTEND  (Next.js)                              │
│                                                                      │
│  OnboardingPanel ──► MapPanel ──► ChatPanel ──► EvidenceDrawer       │
│        ▲                ▲               ▲                            │
│     Weights          CivicData       StreamSSE                       │
└────────┬────────────────┬─────────────┬──────────────────────────────┘
         │               │             │
  POST /api/chat   GET /api/civic   GET /api/chat/stream
         │               │             │
┌────────▼────────────────▼─────────────▼──────────────────────────────┐
│                     BACKEND  (FastAPI)                               │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                  Query Crew  (CrewAI)                          │  │
│  │                                                                │  │
│  │  Router ──► [ Crime | Sentiment | GIS | Comparator ]           │  │
│  │                        │                                       │  │
│  │                 Synthesiser  (LLM)                             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                             │                                        │
│          ┌──────────────────┼──────────────────┐                     │
│          ▼                  ▼                  ▼                     │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐             │
│  │  PostgreSQL  │  │  ChromaDB   │  │  LLM Provider    │             │
│  │  (Supabase)  │  │             │  │                  │             │
│  │              │  │  Reddit +   │  │  OpenRouter (✓)  │             │
│  │  suburbs     │  │  PDF chunks │  │  Anthropic       │             │
│  │  bocsar      │  │             │  │  OpenAI          │             │
│  │  sentiment   │  │  MiniLM     │  │                  │             │
│  │  osm/transp. │  │  L6-v2      │  │                  │             │
│  └──────────────┘  └─────────────┘  └──────────────────┘             │
└──────────────────────────────────────────────────────────────────────┘
```

The multi-agent pipeline is detailed in [SYSTEM_OVERVIEW_EN.md](SYSTEM_OVERVIEW_EN.md).

---

## 🚀 Local Setup

### Before you start — what you must have

The system has two hard requirements without which it cannot run:

| Requirement | Why |
| --- | --- |
| **Supabase project** (PostgreSQL + PostGIS) | The backend creates the DB engine at startup. No `DATABASE_URL` → server fails to start. |
| **LLM API key** (OpenRouter by default) | Every chat request calls the LLM. No key → `ValueError` on the first `/api/chat` call. |

Everything else either has a working default (`CHROMADB_PATH`, `FRONTEND_URL`) or is optional.

### Backend

#### Step 1 — Install dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Step 2 — Configure environment** (required)

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set at minimum:

```bash
DATABASE_URL=postgresql://user:password@host:5432/postgres   # Supabase Session Pooler URL
OPENROUTER_API_KEY=sk-or-...                                  # or ANTHROPIC_API_KEY / OPENAI_API_KEY
```

See the [Environment Variables](#-environment-variables) section for the full reference.

**Step 3 — Apply database migrations** (required on first run)

```bash
cd backend
alembic upgrade head
```

**Step 4 — Download the ChromaDB snapshot** (required for chat to work)

`data/chromadb/` is gitignored. Rebuilding from source takes ~10 hours. Download the prebuilt snapshot instead:

1. Open the latest `chromadb-snapshot-*` release on [GitHub Releases](https://github.com/Nelkit/sydney-liveability-ai/releases).
2. Download `chromadb-snapshot.zip` (~156 MB).
3. Extract into the repo root so files land at `data/chromadb/`.

The backend reads from this path automatically (`CHROMADB_PATH` defaults to `./data/chromadb`).

#### Step 5 — Start the backend

```bash
cd backend
make dev
```

Backend runs at `http://127.0.0.1:8000`. Quick health check:

```bash
curl http://127.0.0.1:8000/health
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

`NEXT_PUBLIC_API_URL` defaults to `http://127.0.0.1:8000`, so no changes to `.env.local` are needed for a local setup where the backend runs on the default port.

Frontend runs at `http://localhost:3000`.

### Notebooks

```bash
cd notebooks
python -m venv venv-notebooks
source venv-notebooks/bin/activate  # Windows: venv-notebooks\Scripts\activate
pip install -r requirements.txt
jupyter notebook
```

Keep the notebook virtualenv separate from the backend `venv` — they share some packages but at different versions.

VS Code option: install the Python and Jupyter extensions, open any `.ipynb`, and select the `notebooks/venv-notebooks` kernel.

---

## 🔐 Environment Variables

Copy the templates and fill in the values:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Windows PowerShell:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

### Backend (`backend/.env`)

**Required — the backend will not start or function without these:**

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string. Use the Supabase **Session Pooler** URL (port **5432**, not 6543). |
| `OPENROUTER_API_KEY` | API key for OpenRouter — required when `LLM_PROVIDER=openrouter` (the default). |

**Required — set one key depending on the provider you choose:**

| Variable | Description |
| --- | --- |
| `ANTHROPIC_API_KEY` | Required when `LLM_PROVIDER=anthropic`. |
| `OPENAI_API_KEY` | Required when `LLM_PROVIDER=openai`. |

**Optional — have working defaults for local development:**

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `openrouter` | LLM provider: `openrouter`, `anthropic`, or `openai`. |
| `LLM_MODEL` | `nvidia/nemotron-3-super-120b-a12b:free` | Model identifier passed to the provider. |
| `CHROMADB_PATH` | `./data/chromadb` | Path to the ChromaDB snapshot, relative to repo root. |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend origin for CORS. |
| `SYNTHESIS_DEBUG_MODE` | `off` | Synthesiser bypass: `off`, `gis`, or `all`. |
| `LLM_AGENT_MODELS_JSON` | _(none)_ | JSON map for per-agent model overrides, e.g. `{"synthesiser": "claude-3-5-sonnet"}`. |

**Not needed for the app — ingestion only:**

| Variable | Description |
| --- | --- |
| `WALKSCORE_API_KEY` | Only required to re-run `ingest_walkscore.py`. Not used at runtime. |

### Frontend (`frontend/.env.local`)

**Optional — has a working default for local development:**

| Variable | Default | Description |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Backend base URL. Only change this if the backend runs on a different host or port. |
| `NEXT_PUBLIC_APP_VERSION` | _(from `package.json`)_ | Version string shown in the UI. |

---

## 🧪 RAG Evaluation Harness

Two evaluation scripts are provided.

### `evaluation/evaluate_rag.py` — end-to-end RAG response evaluator

Runs 15 fixed questions through the live `/api/chat` endpoint and writes full response payloads to `data/eval/rag_evaluation.json`. Questions cover 6 tiers: demo suburbs, sparse-data suburbs, high-density suburbs, cross-suburb comparisons, and an out-of-scope refusal probe.

```bash
# Run against local backend (default)
python evaluation/evaluate_rag.py

# Run against production endpoint
python evaluation/evaluate_rag.py --endpoint https://sydney-liveability-ai.vercel.app/api/chat

# Print summary of an existing results file without re-running
python evaluation/evaluate_rag.py --summarise-only

# Summarise results separately
python evaluation/summarise_rag.py
```

Environment variable override:

```bash
EVAL_ENDPOINT=https://... python evaluation/evaluate_rag.py
```

Output: `data/eval/rag_evaluation.json`

### `backend/scripts/run_agent_eval.py` — LLM-judge retrieval grounding evaluator

Reads prompts from `data/eval/prompts.yaml`, runs each through the full agent pipeline, uses an LLM judge to verify whether factual claims are supported by the evidence trace, and writes verdicts to `data/eval/results.csv`. This produces the retrieval-grounding numbers reported in the AT2B report.

```bash
python backend/scripts/run_agent_eval.py
```

The backend virtualenv must be active with `DATABASE_URL` and `CHROMADB_PATH` set before running this script.

---

## 🗃️ Data Sources

| Source | Type | Volume | Script |
| --- | --- | --- | --- |
| [BOCSAR](https://www.bocsar.nsw.gov.au/) NSW crime statistics | Crime counts by suburb/year | 2024–2025 snapshot | `backend/scripts/ingest_bocsar.py` |
| City of Sydney ArcGIS REST API | Facilities, walkability score | 2026 snapshot | `backend/scripts/ingest_arcgis.py` |
| OpenStreetMap via Overpass API | Amenity counts (cafe, gym, park, etc.) | 2026 snapshot | `backend/scripts/ingest_osm.py` |
| Reddit r/sydney via PRAW / Arctic Shift | Resident discourse | 20,423 records, 563 suburbs | `backend/scripts/ingest_reddit.py` |
| TfNSW GTFS feeds | Transport stops, service frequency | 48,195 stops, 656 suburbs | `backend/scripts/ingest_transport.py` |
| City of Sydney community PDFs | Demographic/housing narratives | 1,114 ChromaDB chunks | `backend/scripts/ingest_pdf.py` |

Processed data lives in `data/processed/` (CSV/JSON) and `data/chromadb/` (vector index). Raw files are not committed; the prebuilt ChromaDB snapshot is available on GitHub Releases (see [Local Setup](#local-setup)).

---

## 🤖 NLP Pipeline and Models

### Sentiment analysis (Agentic RAG)

The sentiment agent is a fully agentic RAG loop implemented in `backend/agents/query/`. The LLM controls its own retrieval strategy via three tools:

- `search_posts(suburb, dimension, query, k)` — semantic search over ChromaDB
- `get_suburb_aspect(suburb, dimension)` — cached score from PostgreSQL
- `compare_suburbs(suburbs, dimension)` — rank suburbs by aspect score

**Offline NLP pipeline** (`backend/core/nlp/pipeline.py`): four staged modules — BART-MNLI zero-shot aspect classification → DeBERTa-v3 ABSA (0.55 confidence floor, 10-word minimum) → GoEmotions emotion profiling → MiniLM-based coverage detection with cross-modal fallback to BOCSAR/OSM/ArcGIS for silent dimensions.

**8 liveability dimensions:** safety, food_and_cafe, nightlife, affordability, transport, community, noise, green_space

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, cosine similarity)

**Chunking:** `RecursiveCharacterTextSplitter`, 200 characters, 20-character overlap

**Sentiment thresholds:** positive ≥ 0.65 · negative ≤ 0.45 · neutral: 0.45–0.65

### Emotion profiles

7-class emotion detection (joy, surprise, neutral, sadness, anger, fear, disgust) stored in the `emotion_profiles` table via the GoEmotions model.

### Traditional NLP (notebooks)

Exploratory analysis in `notebooks/` uses NLTK, VADER, TextBlob, Gensim LDA, scikit-learn TF-IDF, and pyLDAvis. These inform the production pipeline but are not in the serving path.

### Scoring formula

Liveability scores are computed in [`backend/core/scoring.py`](backend/core/scoring.py):

```text
liveability = (safety        × w_safety)
            + (transport     × w_transport)
            + (lifestyle     × w_lifestyle)
            + (affordability × w_affordability)
            + (nightlife     × w_nightlife)
            + (proximity     × w_proximity)
```

Default weights: safety=transport=lifestyle=affordability=0.25, nightlife=proximity=0.0. All components normalised to [0.0, 1.0]. Full breakdown in [SYSTEM_OVERVIEW_EN.md § 4.3](SYSTEM_OVERVIEW_EN.md).

---

## 🔄 Ingestion Pipeline

Run ingestion scripts from the **repo root** after activating the backend virtualenv. Each script is idempotent — re-running it upserts rather than duplicates.

```bash
source venv/bin/activate
```

### Structured data (PostgreSQL tables)

```bash
# Crime statistics → bocsar table
python backend/scripts/ingest_bocsar.py

# City of Sydney facilities + walkability → suburbs table
python backend/scripts/ingest_arcgis.py

# OSM amenity counts → osm_scores table
python backend/scripts/ingest_osm.py

# TfNSW transport data → transport_scores table
python backend/scripts/ingest_transport.py

# Community PDF narratives → chromadb (pdf source)
python backend/scripts/ingest_pdf.py

# Sentiment scores from NLP pipeline → sentiment_scores + emotion_profiles tables
python backend/scripts/ingest_sentiment_postgres.py
```

### ChromaDB (vector index)

These two scripts populate the `sydney_liveability` ChromaDB collection. Run them only if rebuilding the index from raw data (~10 hours; the prebuilt snapshot is recommended).

```bash
# Reddit posts/comments → ChromaDB (source=reddit)
python backend/scripts/ingest_reddit.py

# Sentiment narratives + curated quotes → ChromaDB (source=sentiment_narrative / sentiment_quote)
python backend/scripts/ingest_sentiment.py
```

Optional flags (both scripts):

```bash
--input-dir PATH      # override default input directory
--batch-size N        # ChromaDB upsert batch size
--suburb-limit N      # process only first N suburbs (for smoke tests)
```

---

## ⚠️ Known Limitations

- **Static data.** All datasets (Reddit, BOCSAR, OSM, GTFS) are point-in-time snapshots from 2024/2026. There is no automated update pipeline.
- **ChromaDB rebuild time.** Rebuilding the vector index from scratch takes ~10 hours. Use the prebuilt snapshot for local evaluation.
- **Supabase connection limit.** The free/basic plan allows 15 connections on the Session Pooler. Under high concurrent load the `/api/civic` endpoint may return 503 before the cache warms.
- **Uneven Reddit coverage.** Popular suburbs (Newtown, Glebe, Surry Hills) have many ChromaDB chunks; peripheral suburbs have few or none. Suburbs with sparse data default to a neutral score of 0.5.
- **Fragile router.** The query router is deterministic (regex + keywords). Atypical phrasing may not trigger the correct specialist agents.
- **No authentication.** User weights are stored in `localStorage` only. All users share the same backend instance.
- **Pipeline latency.** Depending on the LLM model and question complexity, the multi-agent pipeline takes 5–15 seconds. SSE streaming mitigates perceived latency.

---

## 👥 Team

Group 3 — ANLP 36118 (UTS)

| Member | Primary contributions |
| --- | --- |
| Ying-Kai Liao | Reddit extraction (PRAW + Arctic Shift), offline NLP pipeline (BART-MNLI, DeBERTa-v3 ABSA, GoEmotions), Sentiment agent rework as CrewAI ReAct A-RAG |
| Padmasri Srinivas | TfNSW GTFS transport pipeline (656 suburbs), RAG evaluation harness (`evaluation/evaluate_rag.py`) |
| Nian-Ya Weng | BOCSAR crime data pipeline, Crime agent (`backend/agents/query/crime.py`), EDA notebooks |
| Nelkit Chavez | FastAPI endpoint architecture, Synthesiser agent, scoring formula + in-memory cache, ArcGIS ingestion, full frontend (OnboardingPanel, MapPanel, EvidenceDrawer, ReportModal) |
| Juan David Rodriguez | PDF ingestion pipeline (1,114 ChromaDB chunks), Synthesiser's ChromaDB retrieval layer |
| Luis Gerardo Robinson | OSM extraction (Overpass API, 657 suburbs), GIS agent (`backend/agents/query/gis.py`), Comparator agent |

---

## 🔗 Links

- [Poster (Figma)](https://www.figma.com/design/eBDd4sDvIbWX61pE25RYkK/Sydney-Liveability-AI%E2%80%94Poster?node-id=1-2&t=LRnrogOncMyVH9Si-1)
- [Project planning (Notion)](https://www.notion.so/nelkitdev/Sydney-Liveability-AI-Project-3370093b498b806c9b28cd35348e208e?source=copy_link)
- Full system documentation: [SYSTEM_OVERVIEW_EN.md](SYSTEM_OVERVIEW_EN.md)

---

Subject: ANLP 36118 | Master of Data Science and Innovation | University of Technology Sydney (UTS)
