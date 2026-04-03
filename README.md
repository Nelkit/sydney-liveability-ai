# Sydney Liveability AI
An AI-assisted, map-based web application to compare Sydney suburbs using civic data, crime statistics, and resident discourse.

## Table of Contents
- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Branch Convention](#branch-convention)
- [Team](#team)

## Overview
- Scope: ANLP 36118 project (UTS), Autumn 2026.
- MVP suburbs: Newtown, Glebe, Redfern, Surry Hills, Haymarket.
- Current backend status: boilerplate endpoints are available at `/` and `/health`.

## Repository Structure

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
│   └── requirements.txt
│
├── frontend/                     # Next.js frontend
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── tailwind.config.ts
│
├── data/                         # Local datasets (ignored in Git)
│   ├── raw/
│   └── processed/
│       └── suburbs.geojson       # Committed static geometry
│
├── AGENTS.md
├── .gitignore
└── README.md
```

## Tech Stack
- Frontend: Next.js, Tailwind CSS, Leaflet.js, Turf.js, Framer Motion.
- Backend: FastAPI, uvicorn, Supabase.
- Backend NLP: LangChain, ChromaDB, Claude API (`claude-sonnet-4-20250514`), sentence-transformers, pypdf, PRAW, spaCy, geopandas.
- Notebooks NLP/EDA: NLTK, Gensim, scikit-learn, VADER, TextBlob, pyLDAvis, Matplotlib, Seaborn.

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- Supabase account
- Anthropic API Key

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

Quick checks:
```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:3000` (or the port shown in terminal).

### 3. Notebooks Setup
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

Important: keep backend and notebooks in separate virtual environments. Do not install notebook-only packages into `backend/venv`.

## Environment Variables
Create environment files from templates at repository root:

```bash
cp .env.backend.example backend/.env
cp .env.example notebooks/.env
```

Windows PowerShell:

```powershell
Copy-Item .env.backend.example backend/.env
Copy-Item .env.example notebooks/.env
```

Then fill values in both files.

## Branch Convention
- Direct commits, pushes, or changes to `main` are prohibited.
- Each student must work on a personal branch prefixed with their name.

Workflow:
```bash
git checkout main
git pull origin main
git checkout -b yourname/short-task-name
git add .
git commit -m "feat: clear summary of change"
git push -u origin yourname/short-task-name
```

Open a Pull Request from your branch to the team integration branch.

## Team
Group 3 — ANLP 36118 (UTS)

- Ying-Kai Liao
- Padmasri Srinivas
- Nian-Ya Weng
- Nelkit Chavez
- Juan David Rodriguez
- Luis Gerardo Robinson

---

Subject: ANLP 36118 | Master of Data Science and Innovation | University of Technology Sydney (UTS)


