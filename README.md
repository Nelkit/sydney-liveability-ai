# Sydney Liveability AI
[![Frontend: Next.js](https://img.shields.io/badge/Frontend-Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vector Store: ChromaDB](https://img.shields.io/badge/VectorStore-ChromaDB-FF6F00?style=flat)](https://www.trychroma.com/)
[![RAG: LangChain](https://img.shields.io/badge/RAG-LangChain-121212?style=flat)](https://langchain.com/)

An AI-assisted, map-based web application to compare Sydney suburbs using civic data, crime statistics, and resident discourse.

## 📚 Table of Contents
- [🧭 Overview](#-overview)
- [🗂️ Repository Structure](#-repository-structure)
- [🛠️ Tech Stack](#-tech-stack)
- [🚀 Getting Started](#-getting-started)
- [🤖 Skills Usage](#-skills-usage)
- [🐞 VS Code Launch Profiles](#-vs-code-launch-profiles)
- [🧪 SYNTHESIS_DEBUG_MODE](#-synthesis_debug_mode)
- [🔐 Environment Variables](#-environment-variables)
- [🌿 Branch Convention](#-branch-convention)
- [👥 Team](#-team)

## 🧭 Overview
- Scope: ANLP 36118 project (UTS), Autumn 2026.
- Suburb coverage: all suburbs available in the current backend datasets.
- Current backend status: the main app flow is connected to `/api/chat` and `/api/civic`; the backend keeps `/` and `/health` available for local checks.

## 🗂️ Repository Structure

```text
sydney-liveability-ai/
│
├── data_extraction/              # Data acquisition and preprocessing scripts
│   ├── extract_reddit.py
│   ├── extract_arcgis.py
│   ├── parse_pdf.py
│   └── process_bocsar.py
│
├── notebooks/                    # EDA and model training only
│   ├── 01_eda_and_cleaning.ipynb
│   ├── 02_traditional_nlp.ipynb
│   ├── 03_topic_modeling.ipynb
│   ├── 04_modern_nlp.ipynb
│   └── requirements.txt
│
├── backend/                      # FastAPI production backend
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
│
├── frontend/                     # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   └── components/
│   │       └── liveability/
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   └── vercel.json
│
├── data/                         # Local datasets (ignored in Git)
│   ├── raw/
│   └── processed/
│       └── suburbs.geojson       # Committed static geometry
│
├── AGENTS.md
├── README.md
├── .gitignore
└── .env.example
```

## 🛠️ Tech Stack
- Frontend: Next.js, Tailwind CSS, Leaflet.js, Turf.js, Framer Motion.
- Backend: FastAPI, uvicorn, Supabase.
- Backend NLP: LangChain, ChromaDB, configurable LLM provider/model via `backend/.env.example`, sentence-transformers, pypdf, PRAW, spaCy, geopandas.
- Notebooks NLP/EDA: NLTK, Gensim, scikit-learn, VADER, TextBlob, pyLDAvis, Matplotlib, Seaborn.

## 🚀 Getting Started
### ✅ Prerequisites
- Python 3.10+
- Node.js 18+
- Supabase account
- OpenRouter API key
- Optional: Anthropic API key or OpenAI API key if you switch providers in `backend/.env`

### 1. 🧩 Backend Setup
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd backend
make dev
```

Backend URL: `http://127.0.0.1:8000`

Quick checks:
```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
```

### 2. 🎨 Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:3000` (or the port shown in terminal).

### 3. 📓 Notebooks Setup
```bash
cd notebooks
python -m venv venv-notebooks
source venv-notebooks/bin/activate  # Windows: venv-notebooks\Scripts\activate
pip install -r requirements.txt
jupyter notebook
```

Open the URL printed by Jupyter (commonly `http://localhost:8888/tree` with token).

VS Code option:
1. Install extensions: Python, Jupyter.
2. Open any `.ipynb` in `notebooks/`.
3. Select kernel from `notebooks/venv-notebooks`.

Important: keep backend and notebooks in separate virtual environments. Do not install notebook-only packages into the backend `venv`.

## 🤖 Skills Usage

This project includes team skills under `skills/` to standardize common implementation tasks.

Use skills in chat with slash-style invocation:

- `/query-agent` for creating or updating specialists in `backend/agents/query/`
- `/ingest-script` for ingestion workflows in `backend/scripts/ingest_*.py`
- `/chromadb-embed` for chunking/embedding/upsert flows in ChromaDB
- `/alembic-migration` for ORM and Alembic migration changes in `backend/db/models.py`
- `/frontend-guard` for new or refactored UI components with strict typing and existing Tailwind design consistency

Pattern:

- `/name-of-skill` where `name-of-skill` matches the folder under `skills/`
- Example: `/query-agent` loads `skills/query-agent/SKILL.md`

If one task spans multiple domains, invoke skills in sequence (for example: `/alembic-migration` then `/ingest-script`).

## 🐞 VS Code Launch Profiles

Shared launch profiles are configured in `.vscode/launch.json`.

- `Frontend: Next dev`
	- Runs `npm run dev` in `frontend/`
	- Opens the local app URL automatically when Next.js prints "Local"
- `Backend: FastAPI dev`
	- Runs `python -m uvicorn main:app --reload` in `backend/`
	- Uses `${workspaceFolder}/venv/bin/python`
	- Opens the backend URL automatically when Uvicorn starts

How to run:

1. Open Run and Debug in VS Code
2. Select one of the profiles above
3. Press F5

If the backend profile fails due to interpreter path, recreate or activate the root `venv` and retry.

## 🧪 SYNTHESIS_DEBUG_MODE

`SYNTHESIS_DEBUG_MODE` is read from `backend/.env` and used by `backend/agents/query/synthesiser.py`.

Supported modes currently implemented:

- `off`: normal synthesiser flow (default)
- `gis`: bypass synthesis and return GIS structured output
- `all`: bypass synthesis and return consolidated outputs from router/crime/sentiment/gis/comparator

How to enable or disable:

1. Edit `backend/.env` and set `SYNTHESIS_DEBUG_MODE=off|gis|all`
2. Restart backend (launch profile or `make dev`) so environment values reload
3. Call `/api/chat` and inspect the response payload

Important:

- Values like `crime`, `sentiment`, or `comparator` are not currently implemented as dedicated passthrough modes
- Unsupported values behave effectively like `off`

## 🔐 Environment Variables
Create environment files from the correct templates in each app folder:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Windows PowerShell:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Then fill values in both files.

Backend variables defined in `backend/.env.example`:

```text
LLM_PROVIDER
LLM_MODEL
OPENROUTER_API_KEY
DATABASE_URL
CHROMADB_PATH
FRONTEND_URL
SYNTHESIS_DEBUG_MODE
ANTHROPIC_API_KEY
OPENAI_API_KEY
LLM_AGENT_MODELS_JSON
```

Frontend variables defined in `frontend/.env.example`:

```text
NEXT_PUBLIC_API_URL
```

## 🌿 Branch Convention
- Direct commits, pushes, or changes to `main` are prohibited.
- Work on feature branches and open a Pull Request to `develop` when ready.

Branch naming:

- `feature/data`
- `feature/nlp`
- `feature/backend`
- `feature/frontend`

Recommended workflow:

1. Update your local `main` before creating a new branch:

```bash
git checkout main
git pull origin main
```

2. Create a feature branch with the appropriate prefix:

```bash
git checkout -b feature/short-task-name
```

Examples:

- `feature/backend-boilerplate`
- `feature/data-extraction`
- `feature/notebook-cleaning`

3. Commit your work on your personal branch only:

```bash
git add .
git commit -m "feat: clear summary of change"
```

4. Push your branch to remote:

```bash
git push -u origin feature/short-task-name
```

5. Open a Pull Request from your branch to `develop`.

Important:

- Never push directly to `main`.
- Keep working in your feature branch for all contributions.
- Merge only through Pull Request review.

## 👥 Team
Group 3 — ANLP 36118 (UTS)

- Ying-Kai Liao
- Padmasri Srinivas
- Nian-Ya Weng
- Nelkit Chavez
- Juan David Rodriguez
- Luis Gerardo Robinson

---

Subject: ANLP 36118 | Master of Data Science and Innovation | University of Technology Sydney (UTS)

## 🔗 Links of Interest

- Poster: https://www.figma.com/design/eBDd4sDvIbWX61pE25RYkK/Sydney-Liveability-AI%E2%80%94Poster?node-id=1-2&t=LRnrogOncMyVH9Si-1
- Project Planning: https://www.notion.so/nelkitdev/Sydney-Liveability-AI-Project-3370093b498b806c9b28cd35348e208e?source=copy_link


