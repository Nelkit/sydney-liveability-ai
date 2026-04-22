# NLP Pipeline — Reddit Suburb Analysis

Multi-layer NLP pipeline that analyses Reddit posts/comments about Sydney suburbs and produces aspect-based sentiment scores, emotion profiles, and a community narrative.

## Architecture

```
Reddit posts (via PRAW)
       |
       v
+-----------------+    +------------------+
| aspects.py      |    | emotions.py      |   <-- run in parallel
| Zero-shot       |    | Emotion          |
| classification  |    | detection        |
| (BART-MNLI)     |    | (DistilRoBERTa)  |
+--------+--------+    +--------+---------+
         |                      |
         v                      |
+-----------------+             |
| sentiment.py    |             |
| Per-aspect      |             |
| VADER scoring   |             |
+--------+--------+             |
         |                      |
         v                      v
+------------------------------------+
| synthesise.py                      |
| Community narrative                |
| (Mock template / Claude API)       |
+------------------------------------+
         |
         v
    pipeline.py  --> SuburbAnalysis JSON
```

## Modules

### `aspects.py` — Aspect Classification

Uses `facebook/bart-large-mnli` (~1.6 GB) for zero-shot classification into 8 liveability dimensions:

| Dimension | Zero-shot label |
|---|---|
| safety | "safety and crime" |
| food_and_cafe | "food, cafes, and restaurants" |
| nightlife | "nightlife, bars, and entertainment" |
| affordability | "rent, housing affordability" |
| transport | "public transport and commuting" |
| community | "community and neighbourhood vibe" |
| noise | "noise and quiet" |
| green_space | "parks and green spaces" |

Each text can be assigned to multiple aspects (multi-label). The `ASPECT_TAXONOMY` dict is the single source of truth for dimensions, search keywords, and classifier labels.

### `sentiment.py` — Per-Aspect Sentiment

Uses VADER (rule-based, no model download) to score sentiment on a 0-1 scale (0.5 = neutral). Scores are aggregated per aspect using a weighted average where the weight is the Reddit upvote score.

### `emotions.py` — Emotion Detection

Uses `j-hartmann/emotion-english-distilroberta-base` (~250 MB) to classify text into 7 emotions: anger, disgust, fear, joy, sadness, surprise, neutral. Suburb-level profile is the mean across all texts.

### `synthesise.py` — Narrative Synthesis

Two implementations behind a `Synthesiser` protocol:

- **`MockSynthesiser`** (default) — Template that interpolates real scores. Names the top 2 and bottom 2 dimensions.
- **`ClaudeSynthesiser`** — Sends posts + scores to Claude via LangChain. Enable with `USE_CLAUDE_SYNTHESIS=true` in `.env`.

### `pipeline.py` — Orchestration

`analyse_suburb(suburb, posts) -> SuburbAnalysis` runs the full pipeline and returns:

```json
{
  "suburb": "Newtown",
  "post_count": 147,
  "fetched_at": "2026-04-13T07:54:28+00:00",
  "aspects": {
    "food_and_cafe": { "score": 0.87, "mentions": 45 },
    "affordability": { "score": 0.21, "mentions": 38 }
  },
  "emotions": { "joy": 0.42, "anger": 0.12 },
  "narrative": "Reddit discussions about Newtown are most positive about...",
  "sources": [{ "text": "...", "url": "...", "score": 15 }]
}
```

## First Run

Models download automatically on first use (~1.85 GB total). Subsequent runs load from cache at `~/.cache/huggingface/`.

## API Endpoint

Exposed at `GET /api/reddit/{suburb}` via `backend/api/reddit_router.py`. Results are cached in Supabase for 24 hours.

## Dependencies

```
transformers    # zero-shot classification, emotion detection
torch           # transformers backend
vaderSentiment  # rule-based sentiment scoring
langchain-anthropic  # Claude synthesis (optional)
```
