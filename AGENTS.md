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
│   ├── agents/
│   ├── crews/
│   ├── db/
│   ├── scripts/
│   ├── alembic/
│   ├── alembic.ini
│   ├── Makefile
│   └── requirements.txt
├── frontend/               # Next.js application
│   ├── src/
│   │   ├── app/
│   │   └── components/
│   │       └── liveability/
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   └── vercel.json
├── data/                   # Local only — never committed to Git
│   ├── raw/
│   └── processed/
│       └── suburbs.geojson
└── .env.example            # Template for all required environment variables
```

---

## Environment setup

Set up and run backend and notebooks with separate virtual environments.

### Backend environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Use `backend/Makefile` for the standard local backend workflow:

```bash
cd backend
make dev
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

## Agent quick commands

Use these commands first when validating local flows.

```bash
# Backend
cd backend
make dev
make db-upgrade
make db-revision m="describe-change"

# Frontend
cd frontend
npm run dev
npm run lint

# Notebooks (separate environment)
cd notebooks
jupyter notebook
```

Notes for agents:
- Backend dev command is defined in `backend/Makefile` and uses `../venv/bin/uvicorn`.
- Frontend scripts are defined in `frontend/package.json`.
- There is currently no committed automated test suite in this repository. Do not invent test commands.

### VS Code launch profiles

The repository includes shared debug launches in `.vscode/launch.json`.

- `Frontend: Next dev`
  - Runs `npm run dev` in `frontend/`.
  - Opens the local URL automatically when Next.js reports "Local".
- `Backend: FastAPI dev`
  - Runs `python -m uvicorn main:app --reload` in `backend/`.
  - Uses `${workspaceFolder}/venv/bin/python`.
  - Opens the API URL automatically when Uvicorn starts.

How to use:
1. Open Run and Debug in VS Code.
2. Select one of the configured profiles by name.
3. Start with F5.

If the backend launch fails due to interpreter path, recreate or activate the root `venv` and retry.

### SYNTHESIS_DEBUG_MODE (synthesiser debug switch)

`SYNTHESIS_DEBUG_MODE` is read from `backend/.env` and normalized in `backend/agents/query/synthesiser.py`.

Supported modes currently implemented:
- `off`: standard synthesiser path (normal chat synthesis).
- `gis`: bypass synthesis and return only GIS agent structured output.
- `all`: bypass synthesis and return consolidated outputs from router/crime/sentiment/gis/comparator.

Practical usage:
1. Set `SYNTHESIS_DEBUG_MODE=off|gis|all` in `backend/.env`.
2. Restart backend launch/session to reload env values.
3. Call `/api/chat` and inspect the response shape.

Important:
- Values such as `crime`, `sentiment`, or `comparator` are not currently implemented as dedicated debug passthrough modes in code.
- Any unsupported value behaves effectively like `off`.

---

## Agent orientation links

Prefer linking these files instead of duplicating behavior notes across instruction files:

- `README.md` — onboarding and local setup.
- `backend/Makefile` — backend run and migration commands.
- `backend/api/chat.py` — `/api/chat` response contract and graceful fallback behavior.
- `backend/api/civic.py` — weight validation and GeoJSON scoring output.
- `backend/crews/query_crew.py` — specialist routing orchestration and out-of-scope short-circuit.
- `backend/agents/query/router.py` — dynamic suburb detection from database values.
- `backend/agents/query/synthesiser.py` — final synthesis payload shaping.
- `backend/db/models.py` — schema fields, including `sa4_area` and geometry support.
- `skills/query-agent/SKILL.md` — implementation standard for query agents.
- `skills/ingest-script/SKILL.md` — ingestion and idempotent upsert workflow.

---

## Common execution pitfalls for AI agents

- Do not hardcode suburb names in router logic; use dynamic suburb support from the database.
- Keep Turf.js and Leaflet coordinate ordering distinct when transforming coordinates.
- Preserve fixed API contracts for `/api/chat`, `/api/civic`, and `/api/comparison`.
- Keep backend and notebook dependencies isolated in separate virtual environments.
- Never hardcode agent model strings; resolve through `get_agent_llm(agent_name)` and environment configuration.

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
- Ingestion scripts live in `backend/scripts/` and must follow the project skills for idempotent upserts and migration-safe writes.
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

All required variables must be present in the correct environment templates (`backend/.env.example` for backend and `frontend/.env.example` for frontend). Never hardcode any of these values in source code:

```
LLM_PROVIDER=
LLM_MODEL=
OPENROUTER_API_KEY=
DATABASE_URL=
CHROMADB_PATH=
FRONTEND_URL=
SYNTHESIS_DEBUG_MODE=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
LLM_AGENT_MODELS_JSON=
NEXT_PUBLIC_API_URL=
```

---

## Claude API usage

- Never hardcode model strings in agent code.
- Query agents must resolve models through `get_agent_llm(agent_name)` and use the shared default from `backend/.env` unless `LLM_AGENT_MODELS_JSON` overrides it.
- If the team changes the shared model, update the environment configuration rather than editing individual agents.
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

## Current implementation scope

Use this section as the source of truth for what an agent should assume is already wired:

- Frontend main flow is implemented in `frontend/src/app/page.tsx` and connected to `/api/chat` and `/api/civic`.
- Core liveability UI components under `frontend/src/components/liveability/` are active and should be evolved, not rewritten blindly.
- Backend query orchestration and routing are implemented under `backend/crews/query_crew.py` and `backend/agents/query/`.
- Backend bootstrap endpoints `GET /` and `GET /health` are available and should remain stable.

Do not keep speculative "missing" lists in this file. If implementation status changes, update this section with verified facts only.

---

## Project skills

| Skill Name | Description | Path |
|---|---|---|
| `ingest-script` | Standard workflow to create `backend/scripts/ingest_*.py` with idempotent upserts, migration-safe steps, and team-ready documentation. | `skills/ingest-script/SKILL.md` |
| `query-agent` | Standard workflow to implement CrewAI agents in `backend/agents/query/` using `get_agent_llm`, DB tools with `get_session()`, and isolated `run(input_data)` execution. | `skills/query-agent/SKILL.md` |
| `chromadb-embed` | Standard workflow to embed text and upsert chunks into ChromaDB with deterministic IDs and required metadata for RAG. | `skills/chromadb-embed/SKILL.md` |
| `alembic-migration` | Standard workflow to add or modify SQLAlchemy ORM fields using Alembic migrations and keep PostgreSQL schema synchronized. | `skills/alembic-migration/SKILL.md` |
| `frontend-guard` | Standard workflow to keep frontend changes aligned with existing Tailwind design language, strict TypeScript typing, and current page-level state architecture. | `skills/frontend-guard/SKILL.md` |

### How to use skills in chat

Use skills explicitly from chat with slash-style invocation:

- `/query-agent` when creating or updating specialists in `backend/agents/query/`.
- `/ingest-script` when creating or refactoring `backend/scripts/ingest_*.py`.
- `/chromadb-embed` when implementing chunking/embedding/upsert workflows.
- `/alembic-migration` when changing `backend/db/models.py` and generating migrations.
- `/frontend-guard` when creating or refactoring UI components in `frontend/src/components/liveability/` with strict typing and style consistency.

Pattern:
- `/name-of-skill` where `name-of-skill` matches the folder under `skills/`.
- Example: `/query-agent` loads `skills/query-agent/SKILL.md`.

Expected workflow:

1. Invoke the relevant skill first.
2. Execute only the scoped task for that skill.
3. Keep API contracts and architecture rules from this file unchanged unless explicitly requested.

If a task touches multiple domains, invoke multiple skills in sequence (for example: `/alembic-migration` then `/ingest-script`).

---

## Team

Group 3 · ANLP 36118 · UTS Master of Data Science and Innovation · Autumn 2026

Ying-Kai Liao · Padmasri Srinivas · Nian-Ya Weng · Nelkit Chavez · Juan David Rodriguez · Luis Gerardo Robinson