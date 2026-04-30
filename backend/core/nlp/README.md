# NLP Pipeline — Reddit Suburb Analysis

Multi-layer NLP pipeline that analyses Reddit posts/comments about Sydney suburbs and produces per-dimension aspect-based sentiment scores, coverage tiers, cross-modal fallbacks, emotion profiles, and a community narrative.

## Architecture

```
Reddit posts (via PRAW)
       |
       v
+-----------------+   +------------------+   +------------------+
| aspects.py      |   | emotions.py      |   | coverage.py      |
| Zero-shot       |   | Emotion          |   | Sentence-tx      |
| classification  |   | detection        |   | similarity       |
| (BART-MNLI)     |   | (DistilRoBERTa)  |   | (MiniLM)         |
+--------+--------+   +--------+---------+   +--------+---------+
         |                     |                      |
         v                     |                      |
+-----------------+            |                      |
| sentiment.py    |            |                      |
| Per-aspect      |            |                      |
| ABSA scoring    |            |                      |
| (DeBERTa-v3)    |            |                      |
+--------+--------+            |                      |
         |                     |                      |
         v                     |                      |
+------------------------------------+                |
| pipeline.py — orchestration        | <- coverage ---+
| - per-dim confidence               |
| - cross-modal fallback (fallback.py)|
+--------+--------+------------------+
         |
         v
+------------------------------------+
| synthesise.py — community narrative|
+------------------------------------+
         |
         v
   SuburbAnalysis JSON
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

Each text can be assigned to multiple aspects (multi-label). The `ASPECT_TAXONOMY` dict is the single source of truth.

### `coverage.py` — Per-Dimension Coverage Detection

Encodes each post and a hand-written prototype sentence per dimension with `all-MiniLM-L6-v2`. The mean of the top-10 cosine similarities maps to a tier:

| Mean top-10 cosine | Tier |
|---|---|
| `< 0.25` | `none` |
| `0.25 – 0.4` | `weak` |
| `> 0.4` | `strong` |

`none` is a first-class value distinct from "Reddit-attested neutral". Thresholds and prototypes live as module-level constants in `coverage.py`.

### `sentiment.py` — Aspect-Based Sentiment (ABSA)

Uses `yangheng/deberta-v3-base-absa-v1.1` (~440 MB) to score sentiment jointly with the aspect span on each `(text, aspect_label)` pair. ABSA replaces the previous VADER lexicon — sarcastic and mixed-aspect Reddit comments are now scored at span level rather than averaged across the whole post.

Posts under 10 words OR with ABSA confidence below `0.55` route to a small-lexicon fallback heuristic with reduced weight in the aggregate (`FALLBACK_WEIGHT_MULTIPLIER = 0.5`).

### `emotions.py` — Emotion Detection

Uses `j-hartmann/emotion-english-distilroberta-base` (~250 MB). Suburb-level profile is the mean across all texts.

### `confidence.py` — Confidence Scoring

- `compute_confidence(post_count)` — legacy global, saturates at 30 posts. Still drives `SuburbAnalysis.confidence` and `confidence_tier`.
- `compute_per_dimension_confidence(mentions)` — saturates at 10 mentions. Surfaced on every aspect entry.
- `MODALITY_CONFIDENCE` — fixed values per cross-modal source: BOCSAR `0.7`, OSM `0.6`, ArcGIS `0.5`, none `0.0`.

### `fallback.py` — Cross-Modal Fallback

`FALLBACK_POLICY` dispatches dimensions whose Reddit `coverage` is `none` to a single per-dim handler:

| Dimension | Handler | Source | Coverage tier when used |
|---|---|---|---|
| safety | `safety_from_bocsar` | `bocsar` | `weak` |
| food_and_cafe | `food_from_osm` | `osm` | `strong` |
| green_space | `green_from_osm_arcgis` | `osm` | `strong` |
| transport | `transport_from_arcgis` | `arcgis` | `weak` |
| community | `community_from_arcgis` | `arcgis` | `weak` |
| nightlife | (none) | `none` | `none`, `score: null` |
| noise | (none) | `none` | `none`, `score: null` |
| affordability | (none) | `none` | `none`, `score: null` |

Reddit-`weak` and Reddit-`strong` dimensions are scored exclusively from Reddit; the policy is invoked only when the suburb is Reddit-silent on that dim. Handlers raise `KeyError` if the suburb is missing from their data; the orchestrator catches and falls through to `null`.

### `synthesise.py` — Narrative Synthesis

Two implementations behind a `Synthesiser` protocol:

- **`MockSynthesiser`** (default) — Template that interpolates real scores.
- **`ClaudeSynthesiser`** — Sends posts + scores to Claude via LangChain. Enable with `USE_CLAUDE_SYNTHESIS=true`.

### `pipeline.py` — Orchestration

`analyse_suburb(suburb, posts) -> SuburbAnalysis` runs aspects/emotions/coverage in parallel, then ABSA per `(text, aspect)` pair, then the cross-modal fallback dispatch, then synthesis.

## Output Schema

```json
{
  "suburb": "Newtown",
  "post_count": 147,
  "fetched_at": "2026-04-13T07:54:28+00:00",
  "aspects": {
    "food_and_cafe": {
      "score": 0.87,
      "mentions": 45,
      "confidence": 1.0,
      "coverage": "strong",
      "source": "reddit"
    },
    "nightlife": {
      "score": null,
      "mentions": 0,
      "confidence": 0.0,
      "coverage": "none",
      "source": "none"
    },
    "safety": {
      "score": 0.62,
      "mentions": 0,
      "confidence": 0.7,
      "coverage": "weak",
      "source": "bocsar"
    }
  },
  "emotions": { "joy": 0.42, "anger": 0.12 },
  "narrative": "Reddit discussions about Newtown are most positive about...",
  "sources": [{ "text": "...", "url": "...", "score": 15 }],
  "confidence": 1.0,
  "confidence_tier": "high"
}
```

`aspects[d].score` is `float | null`. Downstream consumers MUST treat `null` as missing data, not as a numeric value. The agent's `_rank_score` (in `backend/core/agent/nodes.py`) drops `null` dimensions and renormalises weights over the survivors.

## First Run

Models download automatically on first use. Subsequent runs load from cache at `~/.cache/huggingface/`.

| Model | Approx size | Used for |
|---|---|---|
| `facebook/bart-large-mnli` | ~1.6 GB | aspect classification |
| `j-hartmann/emotion-english-distilroberta-base` | ~250 MB | emotion detection |
| `yangheng/deberta-v3-base-absa-v1.1` | ~440 MB | aspect-based sentiment (ABSA) |
| `all-MiniLM-L6-v2` | ~80 MB | dimension-coverage similarity |

First-run cold cost is ~2.4 GB of downloads; warm runs reuse `~/.cache/huggingface/`. The batch precompute script (`python -m data_extraction.precompute_analyses`) is the natural place to bear that cost once per machine.

## API Endpoint

Exposed at `GET /api/reddit/{suburb}` and `GET /api/reddit/summary` via `backend/api/reddit_router.py`. Results are cached locally in `data/processed/reddit_analyses/*.json` and optionally in Supabase.

## Dependencies

```
transformers           # zero-shot, emotion, ABSA pipelines
sentence-transformers  # MiniLM encoder for coverage detection
torch                  # transformers backend
langchain-anthropic    # Claude synthesis (optional)
```
