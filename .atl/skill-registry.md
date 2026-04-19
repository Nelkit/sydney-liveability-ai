# Skill Registry

## Available Skills

| Skill Name | Description | Trigger |
|------------|-------------|---------|
| branch-pr | PR creation workflow for Agent Teams Lite following the issue-first enforcement system. | When creating a pull request, opening a PR, or preparing changes for review. |
| go-testing | Go testing patterns for Gentleman.Dots, including Bubbletea TUI testing. | When writing Go tests, using teatest, or adding test coverage. |
| judgment-day | Parallel adversarial review protocol that launches two independent blind judge sub-agents simultaneously to review the same target, synthesizes their findings, applies fixes, and re-judges until both pass or escalates after 2 iterations. | When user says "judgment day", "judgment-day", "review adversarial", "dual review", "doble review", "juzgar", "que lo juzguen". |
| issue-creation | Issue creation workflow for Agent Teams Lite following the issue-first enforcement system. | When creating a GitHub issue, reporting a bug, or requesting a feature. |
| skill-creator | Creates new AI agent skills following the Agent Skills spec. | When user asks to create a new skill, add agent instructions, or document patterns for AI. |
| ingest-script | Standard workflow to create backend/scripts/ingest_*.py for Sydney Liveability Explorer backend using idempotent upserts and migration-safe steps. | When creating or updating ingestion scripts that write to PostgreSQL tables. |
| query-agent | Standard workflow to implement CrewAI query agents in backend/agents/query/ with get_agent_llm, DB tools via get_session, and isolated run(input_data). | When creating or updating router, crime, sentiment, gis, comparator, or synthesiser agents. |
| chromadb-embed | Standard workflow to embed text and upsert chunks into ChromaDB with deterministic IDs and required metadata for RAG. | When creating or updating embedding helpers for Reddit, PDF, or sentiment text chunks. |
| alembic-migration | Standard workflow to add or modify SQLAlchemy ORM fields using Alembic migrations and keep PostgreSQL schema synchronized. | When changing backend/db/models.py or generating/applying schema migrations. |

## Project Conventions

### /Users/nelkitchavezcalona/Desktop/NLP AT2/sydney-liveability-ai/AGENTS.md

```markdown
# AGENTS.md — Sydney Liveability AI

This file provides context and rules for any AI assistant (Claude, Cursor, GitHub Copilot, ChatGPT, or similar) used by any team member during development. Read this file before generating any code, writing any text, or making any architectural decision.

---

## What this project is

Sydney Liveability AI is a conversational, spatially-aware web application that helps newcomers find the right Sydney neighbourhood. It merges official City of Sydney civic data, BOCSAR crime statistics, and Reddit resident discourse into an interactive map interface. Users ask plain-language questions and receive cited, grounded answers.

This is an academic project submitted for **ANLP 36118 (Autumn 2026) — Master of Data Science and Innovation, UTS**. The submission deadline for Part B (code + report) is **4 May 2026 at 23:59**.

---

## Suburb coverage

The application is no longer limited to five suburbs. Backend routing and civic scoring should work with all suburbs available in the loaded datasets/database.

---

## Repository structure

```
sydney-liveability-ai/
├── data_extraction/        # Python scripts for acquiring raw data
│   ├── extract_reddit.py
│   ├── extract_arcgis.py
│   ├── parse_pdf.py
│   └── process_bocsar.py
├── notebooks/              # Jupyter notebooks for EDA and model training only
│   ├── 01_eda_and_cleaning.ipynb
│   ├── 02_traditional_nlp.ipynb
│   ├── 03_topic_modeling.ipynb
│   ├── 04_modern_nlp.ipynb
│   └── requirements.txt
├── backend/                # FastAPI application — production code only
│   ├── main.py
│   ├── api/
│   ├── core/
│   └── requirements.txt
├── frontend/               # Next.js application
│   └── src/
├── data/                   # Local only — never committed to Git
│   ├── raw/
│   └── processed/
└── .env.example            # Template for all required environment variables
```

---

## Environment setup

Set up and run backend and notebooks with separate virtual environments.

### Backend environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Notebooks environment

```bash
cd notebooks
python -m venv venv-notebooks
source venv-notebooks/bin/activate  # Windows: venv-notebooks\Scripts\activate
pip install -r requirements.txt
jupyter notebook
```

The two virtual environments must be kept separate — never install notebook dependencies into the backend venv or the production deploy will break.

---

## Current backend bootstrap

The backend has a minimal FastAPI boilerplate to validate local setup:

- `GET /` returns project metadata and upcoming endpoints.
- `GET /health` returns `{ "status": "ok" }`.

Keep these routes available while `/api/civic` and `/api/chat` are being built.

---

## Tech stack

Do not introduce new libraries or frameworks without team agreement. The approved stack is:

**Frontend:** Next.js · Tailwind CSS · Leaflet.js · Turf.js · Framer Motion · lucide-react

**Backend (production):** fastapi · uvicorn · langchain · langchain-anthropic · chromadb · sentence-transformers · pypdf · praw · supabase · python-dotenv · pandas · geopandas · shapely · requests

**Notebooks (EDA + training):** fastapi · uvicorn · langchain · langchain-anthropic · chromadb · sentence-transformers · pypdf · praw · supabase · python-dotenv · pandas · geopandas · shapely · requests · nltk · gensim · scikit-learn · spacy · textblob · vaderSentiment · jupyter · matplotlib · seaborn · plotly · wordcloud · pyLDAvis · openpyxl

---

## Architecture rules

### Backend
- All business logic lives in `backend/`. `main.py` is the entry point and must contain no business logic — only router registration, CORS configuration, and startup events.
- Every endpoint lives in `backend/api/` as its own file. Shared utilities (ChromaDB client, scoring logic, prompt templates) live in `backend/core/`.
- The ChromaDB client and pre-computed suburb scores must be loaded once at server startup via `@app.on_event("startup")` — never reloaded per request.
- All endpoints must return graceful error responses. Never return a 500 error to the frontend. Use `try/except` on all external API calls (Claude, ChromaDB, Supabase).
- Dimension weights passed to `/api/civic` must always sum to 1.0. Validate this server-side and return a `400` error with a clear message if they do not.

### Frontend
- All shared state lives in `page.tsx`. Child components (`MapPanel.tsx`, `AssistantSidebar.tsx`, `ComparisonPanel.tsx`) receive state and callbacks as props — they do not manage their own global state.
- Do not delete or rewrite existing components without understanding their current logic first. The frontend already has a functional demo — the task is to connect it to real data, not redesign it.
- Turf.js uses `[longitude, latitude]` coordinate order. Leaflet uses `[latitude, longitude]`. Always double-check coordinate order when passing values between the two libraries.
- Do not persist sensitive data in `localStorage`. Dimension weights for authenticated users must live in Supabase. `localStorage` is only acceptable as a fallback for unauthenticated users.

### Data
- Raw data files go in `data/raw/` and are never committed to Git.
- Processed data files go in `data/processed/` and are never committed to Git.
- The only exception is `data/processed/suburbs.geojson` — this static geometry file must be committed to the repository.
- The ChromaDB `persist_directory` must point to `data/processed/chromadb/`.
- All text chunks ingested into ChromaDB must carry three metadata fields: `suburb` · `source` · `theme`.

### BOCSAR data limitation
The BOCSAR datasets available at [bocsar.nsw.gov.au/statistics-dashboards/open-datasets.html](https://bocsar.nsw.gov.au/statistics-dashboards/open-datasets.html) are structured at SA4 (Statistical Area Level 4), not at suburb level. The only file committed to the repository is `data/raw/bocsar/Statistical_Area_Monthly_Data.xlsx`. Before writing `process_bocsar.py`, check the BOCSAR open datasets page to see whether a more granular suburb-level or LGA-level dataset has become available. If not, use the following confirmed SA4 mapping:

| Suburb | SA4 Area |
|---|---|
| Newtown | Inner West |
| Glebe | Inner West |
| Redfern | City and Inner South |
| Surry Hills | City and Inner South |
| Haymarket | City and Inner South |

This means Newtown and Glebe share the same BOCSAR safety data, and Redfern · Surry Hills · Haymarket share the same BOCSAR safety data. This is a known and documented limitation — not an error. Always include an `sa4_area` field in any processed output so downstream consumers are aware of the data source granularity. Document this limitation explicitly in notebook 01 and in the Evaluation section of the final report.

### Notebooks
- Notebooks are for EDA and model training only. No production logic should live in a notebook.
- All four notebooks must be fully executed with visible outputs before the final submission.
- The preprocessing utility defined in notebook 02 must be reusable across notebooks 03 and 04 — do not duplicate preprocessing code.
- Always set `random_state=42` for any non-deterministic model (LDA, train/test splits).

---

## API response contracts

These response shapes are fixed. Do not change them without updating both the backend and the frontend simultaneously.

### POST /api/chat
```json
{
  "answer": "string",
  "sources": [
    {
      "text": "string",
      "suburb": "string",
      "source": "string"
    }
  ],
  "suburb_scores": {
    "Newtown": 0.78,
    "Glebe": 0.65
  },
  "map_state": {
    "suburb_filter": ["Newtown", "Glebe"],
    "heatmap_weights": {
      "safety": 0.8,
      "transport": 0.2
    }
  }
}
```
`map_state` must be `null` when the query has no spatial intent.

### GET /api/civic
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "suburb": "Newtown",
        "sa4_area": "Inner West",
        "liveability_score": 0.78,
        "safety_score": 0.82,
        "transport_score": 0.74,
        "lifestyle_score": 0.71
      },
      "geometry": { }
    }
  ]
}
```
`sa4_area` is required in every feature. It reflects the BOCSAR data granularity limitation — suburbs within the same SA4 area share the same `safety_score`. Differentiation between those suburbs comes from `transport_score` (ArcGIS) and `lifestyle_score` (VADER sentiment).

### GET /api/comparison
```json
{
  "official": [
    { "text": "string", "theme": "string", "page_number": 0 }
  ],
  "reddit": [
    { "text": "string", "score": 0, "created_utc": 0 }
  ]
}
```

---

## Git rules

- Never push directly to `main`. All work happens on feature branches.
- Branch naming: `feature/data` · `feature/nlp` · `feature/backend` · `feature/frontend`.
- Open a Pull Request to `develop` when a task is ready for review. At least one other team member must approve before merging.
- Never commit: API keys · `.env` files · `data/raw/` · `data/processed/` · `node_modules/` · `venv/` · `.next/`.
- Commit messages must be descriptive. Do not write "fix" or "update" alone — write "fix: suburb weight normalisation in /api/civic" instead.

---

## Environment variables

All required variables must be present in the environment templates (`.env.backend.example` for backend and `.env.example` for notebooks/frontend). Never hardcode any of these values in source code:

```
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=
FRONTEND_URL=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=
```

---

## Claude API usage

- Always use model `claude-sonnet-4-20250514`.
- Always set `max_tokens=1000` for chat responses to keep costs predictable during development.
- The system prompt for `/api/chat` must explicitly instruct the model to: answer only from provided context · cite every claim · return `map_state` when the query has spatial intent · and respond with "I don't have data on that suburb yet" for out-of-scope suburbs.
- Wrap every Claude API call in `try/except`. Return a graceful fallback message on failure — never propagate a raw API error to the frontend.

---

## Writing rules (for report and any documentation)

These rules apply to the technical report, README updates, docstrings, and any written content in this repository:

- Write in academic C1-level English.
- No bullet-point prose in the report — use full sentences and paragraphs.
- No double hyphens (`--`) anywhere. Use an em dash (—) for parenthetical remarks.
- No AI-speak: do not use "delve into" · "it is important to note" · "in conclusion" · "straightforward" · "leverage" as a verb · or "game-changer".
- Every claim in the report must reference either a citation or a specific notebook output.
- The Abstract is written last, after all other sections are complete.
- Do not describe what you planned to build — describe what you actually built.

---

## What is already built

The following is fully implemented and must not be rewritten without team agreement:

- `frontend/src/page.tsx` — full client-side app state flow
- `frontend/src/components/MapPanel.tsx` — interactive Leaflet map with suburb overlays
- `frontend/src/components/AssistantSidebar.tsx` — chat panel with typing indicator
- `frontend/src/components/OnboardingPanel.tsx` — preference onboarding flow
- `frontend/src/components/SharedBrand.tsx` — animated brand component
- `frontend/src/components/TypingDots.tsx` — typing indicator
- `frontend/src/lib/data.ts` — seed data and canned responses (to be replaced by real API calls)
- `frontend/src/lib/utils.ts` — suburb scoring and keyword routing (to be replaced by real API calls)

The current frontend uses static data from `data.ts` and `utils.ts`. The task is to replace those data sources with real API calls — not to redesign the UI.

---

## What still needs to be built

Most of `backend/` · `data_extraction/` · and `notebooks/` still needs implementation. A minimal backend boilerplate is already in place (`/` and `/health`). See the Notion board for the full task list with priorities and dependencies.

---

## Team

Group 3 · ANLP 36118 · UTS Master of Data Science and Innovation · Autumn 2026

Ying-Kai Liao · Padmasri Srinivas · Nian-Ya Weng · Nelkit Chavez · Juan David Rodriguez · Luis Gerardo Robinson
```
