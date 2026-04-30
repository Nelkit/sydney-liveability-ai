# Agent retrieval — tool catalogue and evidence trace

This module provides the retrieval layer for the chat agent. The agent's
`retrieve_agent_node` runs a bounded ReAct loop and selects among the
three tools below at each iteration. Every tool call is logged as a
`TraceEntry` in `state.evidence_trace`, which becomes the report figure
showing the agent's actual decision path for a given user turn.

> **Where the controller lives.** The repo uses **CrewAI**, not
> LangGraph. The retrieval controller is `backend/agents/query/sentiment.py`,
> which calls the three tools below per chat turn and emits an
> `evidence_trace` for the synthesiser to consume. See
> `openspec/changes/add-agentic-rag-synthesiser/design.md` →
> "Implementation deviation" for why we kept the trace contract but
> dropped the LLM-driven ReAct loop in favour of a deterministic
> mini-pipeline.

## Tool catalogue

The agent picks one tool per ReAct iteration. The hard ceiling is **5
tool calls per chat turn**.

### `search_posts(suburb, dimension, query, k=5)`

Dense semantic search over the `sydney_liveability` ChromaDB collection,
filtered by `suburb` (required) and `dimension` (optional). Returns the
top-`k` chunks as `{text, metadata, distance}` tuples sorted by cosine
distance.

**Refuses null dimensions.** If the cached `SuburbAnalysis` for that
suburb has `aspects[dimension].score == null AND source == "none"` (the
upstream pipeline marked the dimension as no-data), the tool short-
circuits with:

```json
{
  "status": "no_data",
  "reason": "no Reddit coverage and no cross-modal proxy",
  "suburb": "<suburb>",
  "dimension": "<dimension>"
}
```

This is the contract that lets the synthesiser verbalise absence
honestly rather than confabulate from tangentially-related chunks.

### `get_suburb_aspect(suburb, dimension)`

Pure structured lookup against the cached `SuburbAnalysis`. Returns
either the full aspect entry (`score, mentions, confidence, coverage,
source`) or `{status: "no_data", ...}` when the dimension is null-scored
(or the suburb is unknown).

### `compare_suburbs(suburbs, dimension)`

Sorts the input list of suburbs descending by
`aspects[dimension].score`. Drops suburbs whose dimension is null-scored
into a `dropped` list (so the synthesiser can verbalise the gap).
Refuses inputs longer than 10 — the agent must use `filter_node`'s
shortlist rather than re-rank the global corpus through this tool.

## Evidence trace shape

`state.evidence_trace` is a list of `TraceEntry` dicts, appended to once
per tool call (including invalid ones):

```python
{
    "step": int,            # 1-indexed iteration number
    "tool": str,            # "search_posts" | "get_suburb_aspect" | "compare_suburbs" | "stop" | "invalid"
    "arguments": dict,      # the parsed JSON arguments the LLM emitted
    "reasoning": str,       # the LLM's "why this tool" string
    "result_count": int,    # 0 for stop / invalid / no_data
    "result_preview": str,  # first ~200 chars of the top result, or the no_data reason
    "elapsed_ms": float,
}
```

The synthesise prompt receives the full trace plus the original
`top_suburbs` ranking. The evaluator receives the trace alongside the
existing weight-trace and uses it to score the new
`retrieval_grounded` rubric criterion.

## Worked example

User: *"Which of Newtown or Glebe has better transport?"*

| Step | Tool | Arguments | Result |
|---|---|---|---|
| 1 | `compare_suburbs` | `{suburbs: ["Newtown", "Glebe"], dimension: "transport"}` | `ranked: [{Newtown: 0.48}, {Glebe: 0.41}]` |
| 2 | `search_posts` | `{suburb: "Newtown", dimension: "transport", query: "bus reliability", k: 3}` | 3 chunks |
| 3 | `search_posts` | `{suburb: "Glebe", dimension: "transport", query: "bus reliability", k: 3}` | 2 chunks |
| 4 | `stop` | `{reason: "have ranking + 5 supporting quotes"}` | — |

The synthesiser then writes a 2-3 sentence answer, citing one chunk from
step 2 and one from step 3.

## Running ingestion

```bash
# Per-suburb Reddit posts → chunks tagged with the BART-MNLI top dimension
python backend/scripts/ingest_reddit.py

# Sentiment narratives + curated quote chunks
python backend/scripts/ingest_sentiment.py
```

Both are idempotent — chunk IDs are deterministic on
`{source}-{post_id_or_hash}-{chunk_index}`, so re-runs upsert in place.
The collection lives at `settings.chromadb_path`
(default `./data/chromadb`).

## Offline evaluation

`backend/scripts/run_agent_eval.py` is the single source of truth for the
report's retrieval-grounding numbers. It runs every prompt in
`data/eval/prompts.yaml` through `crews.query_crew.run_query`, asks an LLM
judge whether every named-suburb claim in the answer is supported by an
`evidence_trace` entry, and writes per-prompt verdicts to
`data/eval/results.csv` (gitignored — script output, not source).

```bash
# Smoke run (first 3 prompts)
python backend/scripts/run_agent_eval.py --limit 3

# Full run (~30 prompts, < 5 min wall clock)
python backend/scripts/run_agent_eval.py

# Force a stronger judge model for the report
python backend/scripts/run_agent_eval.py --judge-model claude-opus-4-7
```

`results.csv` schema (one row per prompt):

| column | type | description |
|---|---|---|
| `id` | str | kebab-case prompt id from `prompts.yaml` |
| `prompt` | str | the user question |
| `answer` | str | the agent's answer text |
| `retrieval_grounded` | bool | judge verdict: every named-suburb claim is supported |
| `expect_grounded` | bool | the labeller's prior verdict, copied from `prompts.yaml` |
| `reason` | str | the judge's free-text rationale |
| `trace_length` | int | total `evidence_trace` entries this turn |
| `n_no_data` | int | trace entries reporting `no_data` |
| `judge_model` | str | model name used by the judge |
| `agent_latency_ms` | float | wall-clock time of `run_query()` in ms |

The judge prompt is uniform across categories (per design §5): an
out_of_scope refusal that names no suburbs is trivially grounded; a
no_data answer that honestly says "I don't have data on …" is grounded;
a fabricated suburb claim is ungrounded.
