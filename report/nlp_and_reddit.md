# Report — Reddit + NLP pipeline (current state)

This section covers the parts of the project that turn unstructured
r/sydney discourse into the grounded retrieval signal the chat agent
actually cites. The pipeline now runs end-to-end from raw extraction to a
populated vector index, an agent that searches it under a 5-tool budget,
and an offline LLM-judge evaluator that produces the report's
retrieval-grounding numbers.

## 1. Data extraction

Two complementary sources feed the same per-suburb JSON shape under
`data/processed/reddit/`:

- **PRAW live extraction** (`data_extraction/extract_reddit.py`). Eight
  aspect-keyword search queries against `r/sydney` per suburb (safety,
  food_and_cafe, nightlife, affordability, transport, community, noise,
  green_space). Filters to `score >= 2` to drop noise.
- **Arctic Shift bulk dump** (`data_extraction/process_arctic_shift.py`).
  An NDJSON archive of historical r/sydney posts, partitioned per suburb
  by string-matching the suburb name and its known variants. This is the
  bulk-of-corpus source — PRAW alone hits Reddit's API limits before
  reaching deep history.

Both pipelines normalise to the same record shape (`text`, `suburb`,
`score`, `created_utc`, `url`, `type`) so downstream code only handles
one schema.

**Coverage**: 565 per-suburb files in `data/processed/reddit/` and 563
matching analysis files in `data/processed/reddit_analyses/` — each is
one suburb's discourse plus the analysis output described below.

## 2. NLP analysis pipeline

`backend/core/nlp/pipeline.py` orchestrates a deterministic per-suburb
analysis whose output (`SuburbAnalysis`) is the contract the rest of the
system reads from. The pipeline runs four transformer-backed stages plus
a cross-modal fallback.

### 2.1 Aspect classification — BART-MNLI zero-shot

`backend/core/nlp/aspects.py` runs `facebook/bart-large-mnli` zero-shot
classification over each chunk against eight liveability dimensions
(`safety`, `food_and_cafe`, `nightlife`, `affordability`, `transport`,
`community`, `noise`, `green_space`). Threshold 0.3; below that a chunk
is tagged `"general"` and excluded from per-aspect aggregation. The label
catalogue is the single source of truth — the same aspect list drives
ingestion tagging, search-time filters, and the agent's dimension
routing.

### 2.2 Aspect-Based Sentiment Analysis — DeBERTa-v3 ABSA

`backend/core/nlp/sentiment.py` replaces the previous whole-text VADER
scoring with `yangheng/deberta-v3-base-absa-v1.1`. ABSA scores the
sentiment of each (text, aspect) pair jointly with the aspect span, so a
single post that says *"the food is great but rent is brutal"* registers
positive `food_and_cafe` and negative `affordability` instead of a
neutral average. Polarity maps to a 0–1 scale (0 negative, 0.5 neutral,
1 positive). Two routing rules guard against ABSA's known weaknesses:

- **Confidence floor at 0.55** — ABSA's softmax peaks above this on
  product-review-shaped text but is overconfident on terse Reddit
  one-liners; below the floor the (text, aspect) pair is routed to the
  BART-MNLI fallback path.
- **Word-count floor of 10** — texts shorter than 10 words skip ABSA
  entirely. The fallback path is also dampened in the aggregate so a
  corpus of short noisy posts can't drown out the longer ABSA-confident
  signal.

### 2.3 Coverage detection — sentence-transformer similarity

`backend/core/nlp/coverage.py` answers a different question from
classification: not *"how is the topic discussed?"* but *"is the topic
discussed at all?"* Each dimension has a hand-written prototype sentence
(e.g. *"public transport, trains, buses, and commuting around the area"*).
We embed every chunk and the prototypes with the shared MiniLM encoder
(`sentence-transformers/all-MiniLM-L6-v2`), take the top-k=10 cosine
similarities per dimension, and tier the average:

| Tier | Threshold | Meaning |
|---|---|---|
| `strong` | mean ≥ 0.40 | enough Reddit signal to score the dimension |
| `weak`   | 0.25 ≤ mean < 0.40 | some chatter; score with reduced confidence |
| `none`   | mean < 0.25 | no Reddit signal at all — fall back or null |

Tier thresholds were tuned against a 30-suburb hand-labelled sample.
This separation matters because *zero ABSA pairs* can mean two things:
either nobody talks about the topic, or the BART-MNLI top label was a
different aspect — coverage distinguishes the two cases honestly.

### 2.4 Emotion profile — DistilBERT GoEmotions

`backend/core/nlp/emotions.py` runs DistilBERT fine-tuned on GoEmotions
to attach an emotion distribution per chunk (anger, joy, sadness, fear,
…). Aggregated to a per-suburb softmax for the chat agent's narrative
hooks. Lightweight relative to ABSA so it runs on every chunk
unconditionally.

### 2.5 Cross-modal fallback

`backend/core/nlp/fallback.py` is the contract for what to do when
Reddit is silent. Each dimension has an explicit handler:

- **safety** → BOCSAR crime-statistic percentile anchor
- **transport, walkability, amenity dimensions** → OSM scores from
  `data/processed/osm_scores.json`
- **demographics-leaning dimensions** → ArcGIS suburb-level rows

The dispatch table `FALLBACK_POLICY` is deliberately a static
per-dimension routing rather than a learned policy so the report can
show the table verbatim. When neither Reddit nor a fallback produces a
signal, the dimension's `score` field is `null` and the `source` field
is `"none"` — the agent treats both consistently as missing data and
refuses to fabricate a number.

### 2.6 Output schema

The pipeline writes one JSON per suburb under
`data/processed/reddit_analyses/`:

```python
SuburbAnalysis = {
    "suburb": str, "post_count": int, "fetched_at": iso8601,
    "aspects": {
        dim: {
            "score": float | None,        # null when missing
            "mentions": int,
            "confidence": float,           # 0..1, modality-adjusted
            "coverage": "none" | "weak" | "strong",
            "source": "reddit" | "bocsar" | "osm" | "arcgis" | "none",
        }
    },
    "emotions": {label: float, ...},       # softmax over 27 GoEmotions
    "narrative": str,                       # LLM summary (synthesise.py)
    "sources": [{text, url, dimension}, ...],
}
```

The explicit `null` score and the `coverage`/`source`/`confidence`
trio are what let the agent verbalise *"I don't have transport data on
Abbotsbury"* instead of inventing one.

## 3. Vector retrieval — ChromaDB

`backend/db/chromadb.py` manages a `sydney_liveability` collection of
~72 000 chunks built by two ingestion scripts:

- **`backend/scripts/ingest_reddit.py`** — reads per-suburb JSON arrays,
  chunks each post with `chunk_reddit_text` (200 tokens, 20 overlap),
  classifies each chunk's top dimension via BART-MNLI (threshold 0.3,
  else `"general"`), and upserts. Chunk IDs are deterministic on
  `(source, post_id, chunk_index)` so re-running the script replaces
  rather than duplicates.
- **`backend/scripts/ingest_sentiment.py`** — ingests the per-suburb
  narrative summaries plus the curated quote chunks from
  `SuburbAnalysis.sources`, tagged `source="sentiment"` so the agent can
  prefer them when looking for clean citations.

Embeddings: `sentence-transformers/all-MiniLM-L6-v2`, shared via
`backend/core/embeddings.py` so coverage detection and ChromaDB use the
same model singleton (saving ~500 MB of repeated loads). Chunk metadata
carries `suburb`, `dimension`, `source`, `url`, and `score` so all
filters can run server-side.

## 4. Agentic retrieval

`backend/core/agent/tools.py` exposes three tools to the chat agent.
The contract is the same as the original LangGraph design even though
the runtime is CrewAI's deterministic mini-pipeline (see
`backend/core/agent/README.md`):

| Tool | Purpose | No-data behaviour |
|---|---|---|
| `search_posts(suburb, dimension, query, k)` | dense semantic search over `sydney_liveability`, filtered by suburb (req.) and dimension (opt.) | refuses with `status: no_data` when the cached `aspects[dimension].score` is `null` and `source == "none"` |
| `get_suburb_aspect(suburb, dimension)` | structured lookup against the cached `SuburbAnalysis` | returns `{status: no_data, ...}` for null dimensions |
| `compare_suburbs(suburbs, dimension)` | sort by `aspects[dimension].score`, drop nulls | refuses inputs longer than 10 |

`backend/agents/query/sentiment.py` is the controller. For each suburb
mentioned by the router it: (a) calls `get_suburb_aspect` once per
dimension to build a structured aspect payload, then (b) makes up to one
question-driven `search_posts` call routed to the dimension whose
keywords best match the question. Every call appends a `TraceEntry` to
`evidence_trace`, which the synthesiser cites and which the offline
evaluator reads. The hard ceiling is 5 question-driven tool calls per
turn (the structured fan-out is unbounded — it's deterministic, not a
ReAct decision).

The synthesiser (`backend/agents/query/synthesiser.py`) gates the
`Evidence trace:` block on `router_output.categories`: out_of_scope
turns drop the block entirely, spatial turns include one line per trace
entry. This is the contract the LLM relies on to know when *not* to
cite, which keeps the polite-refusal path clean.

## 5. Offline retrieval-grounding evaluation

The chat hot-path emits a deterministic `evidence_trace` and a small
`quality.evidence_trace_summary` aggregate (length, per-tool counts,
last action, no_data count) — that's enough for a future debug panel
without an inline LLM judge slowing the user down. Grading happens
out-of-band in `backend/scripts/run_agent_eval.py`:

1. Load the curated 30-prompt set from `data/eval/prompts.yaml`
   (10 spatial-grounded · 10 no-data · 5 multi-suburb · 5 out_of_scope).
2. Run each prompt through `crews.query_crew.run_query`, capturing the
   answer, sources, and full per-suburb evidence trace.
3. Ask one LLM judge per prompt (uniform template, no per-category
   rubric): *"does every named-suburb claim in the answer have a
   supporting trace entry? reply JSON: {retrieval_grounded, reason}"*.
4. Write `data/eval/results.csv` with one row per prompt:
   `id, prompt, answer, retrieval_grounded, expect_grounded, reason,
   trace_length, n_no_data, judge_model, agent_latency_ms`.
5. Print a final summary: `N prompts: K grounded, M ungrounded,
   P agreement-with-prior`.

The judge model is configurable via `--judge-model` (default falls
through `LLM_AGENT_MODELS_JSON["evaluator"]` → `LLM_MODEL`). The script
records the model name per row so the report can show how verdicts
change between, e.g., `gpt-5.4-mini` (cheap, iterable) and
`claude-opus-4-7` (stricter, ~30× cost).

## 6. What the report can defensibly claim

- **Honest no-data**. The `null` score + `source: "none"` contract
  flows through ABSA, coverage, ChromaDB filtering, and the agent's
  refusal logic, so a missing-data verdict at the chat output is
  traceable to a verifiable absence in the analysis JSON.
- **Aspect-level granularity**. ABSA scores each (text, aspect) pair
  separately, so positive food sentiment doesn't get cancelled by
  negative rent sentiment in the same post. This is verifiable in the
  per-suburb `aspects.*.score` distributions.
- **Retrieval grounding is auditable**. Every chat turn emits a full
  evidence trace; every offline eval row records the judge's reasoning
  string. Disagreement between the judge's verdict and the labeller's
  prior (`expect_grounded`) is a single CSV filter away.

## 7. Known limitations

- LLM-judge verdicts on paraphrased citations are noisy. Mitigation:
  log the judge's full reason per row; the report can audit
  disagreements manually rather than build a hand-labelled gold set.
- The 30-prompt set is curated, not sampled, so generalisation claims
  are limited. The eval is framed as *directional retrieval-quality
  evidence*, not a production benchmark.
- The Arctic Shift dump is a snapshot — discourse drift after the dump
  date isn't captured until the next bulk re-ingest.
