# 🌆 Sydney Liveability AI
**An AI-Driven Spatial Liveability Engine**

[![Next.js](https://img.shields.io/badge/Frontend-Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/VectorStore-ChromaDB-FF6F00?style=flat)](https://www.trychroma.com/)
[![LangChain](https://img.shields.io/badge/RAG-LangChain-121212?style=flat)](https://langchain.com/)

Thousands of people move to Sydney each year with no way to know what it’s actually like to live in each suburb. **Sydney Liveability AI** bridges this gap by merging civic infrastructure data, crime statistics, and authentic community voices into an interactive, conversational map interface. 

This project directly aligns with the *Community Strategic Plan: Delivering Sustainable Sydney 2030-2050*, aiming to help residents evaluate neighbourhoods based on the core community values: a city for people, a city that moves, an environmentally responsive city, a lively cultural city, and a future-focused economy.

---

## ✨ Key Features
1. **Conversational Map Control (AI Spatial Interface):** Users don't just chat with text; the AI actively controls the map. Using LangChain and Claude, queries like *"show me safe areas with parks"* generate a conversational response and a JSON state that dynamically updates Leaflet map filters and heatmaps.
2. **Personalised Liveability Profiles:** Integrated with Supabase Auth, users can save custom dimension weights (e.g., 80% Transport, 20% Nightlife) to instantly recalculate suburb scores based on their unique priorities.
3. **Bring Your Own Context:** Users can drop a pin for their workplace or university, allowing the system to evaluate suburbs based on commuting proximity using Turf.js in-browser spatial operations.
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
│   ├── extract_arcgis.py         # REST API calls for City of Sydney infrastructure
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
│   ├── api/                      # Endpoints (e.g., /api/chat, /api/civic)
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
│   ├── raw/                      # Unprocessed CSVs and PDFs
│   └── processed/                # Cleaned JSONs and pre-computed model weights
│
├── .gitignore                    # Ensures large data files & API keys are not committed
└── README.md                     # Project documentation
```

---

## 📊 Verified Data Pillars
*   **Community Insights Report 2024:** The City of Sydney recently reviewed over 13,500 pieces of community feedback and analysed 7,724 open-field survey comments. While the raw survey responses remain private to protect citizens, our pipeline extracts the official thematic findings and direct resident quotes across MVP suburbs (Newtown, Glebe, Redfern, Surry Hills, Haymarket).
*   **Reddit PRAW:** Unstructured social text scraped from `r/sydney`, filtered by suburb tags to capture authentic, unfiltered neighbourhood sentiment.
*   **BOCSAR Crime Stats:** Suburb-level criminal incident data.
*   **City of Sydney ArcGIS:** Geospatial datasets accessed via REST API (Walking Count Sites, Sports Facilities, Open Spaces).

---

## 🧠 NLP Architecture: Traditional vs. Modern
In alignment with the ANLP assessment framework, this project explicitly compares the static outputs of traditional NLP pipelines against the deep contextual understanding of modern Transformer-based LLMs/RAG architectures:

| Technique | Type | Role in Project |
| :--- | :--- | :--- |
| **TF-IDF Keyword Extraction** | Traditional | Identifies top terms per suburb by counting word co-occurrences (e.g., *transport, rent, noise*). |
| **LDA Topic Modelling (Gensim)** | Traditional | Unsupervised discovery of overarching themes (e.g., identifying "Transport" at 78%). |
| **VADER / TextBlob** | Lexicon | Fast, baseline sentiment scoring per suburb and topic. |
| **Sentence Embeddings (MiniLM)**| Modern | Semantic similarity for vectorising PDF quotes and Reddit text into ChromaDB, capturing context that traditional N-grams miss. |
| **LLM (Claude) + RAG** | Modern | Generates synthesised, cited natural language answers dynamically controlling the UI. |

---

## 🛠️ Tech Stack
* **Frontend:** Next.js, Tailwind CSS, Leaflet.js / Mapbox, Turf.js, Recharts/D3.
* **Backend:** Python FastAPI, Supabase (PostgreSQL + Auth).
* **AI / NLP Pipeline:** LangChain, ChromaDB, Claude API (Sonnet-3.5/4.0), `pypdf`, `spaCy`, NLTK, Gensim.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.10+
* Node.js 18+
* Supabase Account & API Keys
* Anthropic Claude API Key or OpenAI API Key

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
*Create a `.env.local` file in both directories according to the `.env.example` templates provided.*

---

## 👥 The Team (Group 3)
Built collaboratively for **ANLP 36118 (Autumn 2026) - Master of Data Science and Innovation, UTS**.

*   **Ying-Kai Liao**
*   **Padmasri Srinivas**
*   **Nian-Ya Weng**
*   **Nelkit Chavez**
*   **Juan David Rodriguez**
*   **Luis Gerardo Robinson**

> **Disclaimer:** This project is submitted as an academic requirement for the University of Technology Sydney (UTS).