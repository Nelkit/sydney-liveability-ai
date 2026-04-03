# 🌆 Sydney Liveability AI
**An AI-Driven Spatial Liveability Engine**

[![Next.js](https://img.shields.io/badge/Frontend-Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/VectorStore-ChromaDB-FF6F00?style=flat)](https://www.trychroma.com/)
[![LangChain](https://img.shields.io/badge/RAG-LangChain-121212?style=flat)](https://langchain.com/)

Thousands of people move to Sydney each year with no way to know what it's actually like to live in each suburb. **Sydney Liveability AI** bridges this gap by merging civic infrastructure data, crime statistics, and authentic community voices into an interactive, conversational map interface.

This project directly aligns with the *Community Strategic Plan: Delivering Sustainable Sydney 2030-2050*, aiming to help residents evaluate neighbourhoods based on the core community values: a city for people, a city that moves, an environmentally responsive city, a lively cultural city, and a future-focused economy.

---

## 🧭 Problem Statement

Newcomers making high-stakes decisions (international students, migrants, interstate movers) face four major challenges:

1. **The Fragmented Information Gap:** Users must choose a suburb with no access to structured resident voices — existing tools only show rental prices or cafe locations.
2. **Hidden Civic Data:** The City of Sydney collects rich data (representing 7,724 open-field resident survey responses), but raw data is private, and the synthesised insights are buried in static 44-page PDFs, making them completely unsearchable.
3. **Disconnected Datasets:** Crime data (BOCSAR), walkability data, and infrastructure data exist in entirely separate portals with no tool connecting them.
4. **Liveability is Subjective:** A young family's priorities differ wildly from an international student's, but current tools offer the exact same generic results for all.

---

## ✨ Key Features

1. **Conversational Map Control (AI Spatial Interface):** Users don't just chat with text — the AI actively controls the map. Using LangChain and Claude, queries like *"show me safe areas with parks"* generate a conversational response and a JSON state that dynamically updates Leaflet map filters and heatmaps.
2. **Personalised Liveability Profiles:** Integrated with Supabase Auth, users can save custom dimension weights (e.g., 80% Transport, 20% Nightlife) to instantly recalculate suburb scores based on their unique priorities.
3. **Bring Your Own Context:** Users weight liveability dimensions, upload rental PDFs for address-level advice, or drop a pin for their workplace to re-rank suburbs by commuting proximity.
4. **Custom RAG for Rental Ads:** Users can upload a PDF of a rental listing. The RAG system cross-references the exact address with local Reddit sentiment and BOCSAR crime stats.
5. **Side-by-Side Source Comparison:** An explicit UI panel that contrasts official City of Sydney report themes with organic Reddit resident discourse for the exact same suburb.

---

## 🗂️ Repository Structure

This repository is structured as a monorepo to encompass the entire end-to-end NLP pipeline — from data acquisition and exploratory model training to the final full-stack web application.

```text
sydney-liveability-ai/
│
├── data_extraction/              # Scripts for acquiring and cleaning raw data
│   ├── extract_reddit.py         # PRAW script for r/sydney scraping
│   ├── extract_arcgis.py         # City of Sydney ArcGIS open data download + processing
│   ├── parse_pdf.py              # pypdf script for Community Insights Report
│   └── process_bocsar.py         # Script to clean and format BOCSAR crime CSVs
│
├── notebooks/                    # Jupyter notebooks for EDA and Model Training
│   ├── 01_eda_and_cleaning.ipynb # Initial data exploration
│   ├── 02_traditional_nlp.ipynb  # TF-IDF keyword extraction & VADER sentiment
│   ├── 03_topic_modeling.ipynb   # Gensim LDA training and topic discovery
│   └── 04_modern_nlp.ipynb       # MiniLM embeddings and RAG pipeline testing
│
├── backend/                      # FastAPI Application (Production API)
│   ├── main.py                   # FastAPI server entry point
│   ├── api/                      # Endpoints (/api/chat · /api/civic · /api/comparison · /api/rental)
│   ├── core/                     # LangChain orchestration & ChromaDB logic
│   └── requirements.txt          # Python dependencies for the backend
│
├── frontend/                     # Next.js Application (User Interface)
│   ├── src/                      # React components, Turf.js logic, Leaflet maps
│   ├── public/                   # Static assets
│   ├── package.json              # Node.js dependencies
│   └── tailwind.config.ts        # UI styling configuration
│
├── data/                         # Local dataset storage (Ignored in Git)
│   ├── raw/
│   │   ├── bocsar/               # Raw BOCSAR Excel files
│   │   ├── arcgis/               # Downloaded City of Sydney ArcGIS datasets
│   │   └── reddit/               # Raw Reddit JSON files per suburb
│   └── processed/
│       ├── bocsar_clean.csv
│       ├── arcgis/               # Cleaned GeoJSON files per dataset
│       ├── community_report.json
│       ├── vader_scores.json
│       ├── lda_topic_mapping.json
│       ├── suburbs.geojson       # ⚠️ Committed to Git — static suburb boundary polygons
│       └── chromadb/             # ChromaDB vector store (persistent)
│
├── AGENTS.md                     # AI assistant context and coding rules for the team
├── .gitignore                    # Ensures large data files & API keys are not committed
└── README.md                     # Project documentation
```

---

## 📊 Verified Data Pillars

- **Community Insights Report 2024:** The City of Sydney analysed over 13,500 pieces of community feedback and 7,724 open-field survey responses. Our pipeline extracts the official thematic findings and direct resident quotes across the 5 MVP suburbs (Newtown · Glebe · Redfern · Surry Hills · Haymarket).
- **Reddit PRAW:** Unstructured social text scraped from `r/sydney`, filtered by suburb tags to capture authentic, unfiltered neighbourhood sentiment.
- **BOCSAR Crime Stats:** SA4 area-level criminal incident data. Our 5 MVP suburbs map to two SA4 areas — `Inner West` (Newtown · Glebe) and `City and Inner South` (Redfern · Surry Hills · Haymarket). This is a known data granularity limitation documented in the evaluation.
- **City of Sydney ArcGIS:** Point-of-interest datasets downloaded from the [City of Sydney Data Hub](https://data-cityofsydney.opendata.arcgis.com), including Sports Facilities and additional infrastructure datasets selected for suburb-level coverage. See `extract_arcgis.py` for the confirmed dataset list.

---

## 🧠 NLP Architecture: Traditional vs. Modern

In alignment with the ANLP assessment framework, this project explicitly compares the static outputs of traditional NLP pipelines against the deep contextual understanding of modern Transformer-based LLMs and RAG architectures:

| Technique | Type | Role in Project |
| :--- | :--- | :--- |
| **TF-IDF Keyword Extraction** | Traditional | Identifies top terms per suburb by counting word co-occurrences (e.g., *transport, rent, noise*). |
| **LDA Topic Modelling (Gensim)** | Traditional | Unsupervised discovery of overarching themes (e.g., identifying "Transport" as dominant). |
| **VADER / TextBlob** | Lexicon | Fast baseline sentiment scoring per suburb and topic. |
| **Sentence Embeddings (MiniLM)** | Modern | Semantic similarity for vectorising PDF quotes and Reddit text into ChromaDB, capturing context that traditional n-grams miss. |
| **LLM (Claude) + RAG** | Modern | Generates synthesised, cited natural language answers that dynamically control the UI. |

---

## 🛠️ Tech Stack

- **Frontend:** Next.js · Tailwind CSS · Leaflet.js · Turf.js · Framer Motion · Recharts/D3
- **Backend:** Python FastAPI · Supabase (PostgreSQL + Auth) · uvicorn
- **AI / NLP Pipeline:** LangChain · ChromaDB · Claude API (`claude-sonnet-4-20250514`) · sentence-transformers (`all-MiniLM-L6-v2`) · pypdf · spaCy · NLTK · Gensim · scikit-learn · PRAW

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Supabase account and API keys
- Anthropic API key

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Create a `.env.local` file in both `backend/` and `frontend/` using `.env.example` as the template.

---

## 👥 The Team (Group 3)

Built collaboratively for **ANLP 36118 (Autumn 2026) — Master of Data Science and Innovation, UTS**.

- Ying-Kai Liao
- Padmasri Srinivas
- Nian-Ya Weng
- Nelkit Chavez
- Juan David Rodriguez
- Luis Gerardo Robinson

> **Disclaimer:** This project is submitted as an academic requirement for the University of Technology Sydney (UTS).