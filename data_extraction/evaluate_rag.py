"""
evaluate_rag.py - Sprint 4 RAG evaluation harness.

Runs a fixed set of test questions through the live /api/chat endpoint
(see backend/api/chat.py for the request/response contract) and records
the full response payload for downstream manual scoring.

Question design
---------------
The 15 questions test the system across data-coverage tiers, not just the
5 demo suburbs:

  Tier 1 (demo, 9 Qs):       Sydney/Surry Hills/Glebe/Eveleigh/Zetland
                             across safety/transport/lifestyle/liveability.
  Tier 2 (sparse_data, 1 Q): Wareemba (1 Reddit post, most aspects empty).
                             Tests whether the system flags low-evidence
                             answers vs. fabricating confident ones.
  Tier 3 (analysed_undemoed, 1 Q): Newtown (in 563-suburb Reddit set, not in
                             the front-map 5). Tests breadth.
  Tier 4 (structured_only, 1 Q): Mount Druitt (BOCSAR + GTFS, no Reddit).
                             Tests cross-source synthesis.
  Tier 5 (comparison, 2 Qs): Cross-suburb comparison within demo set.
  Tier 6 (out_of_scope, 1 Q): Newcastle (different city). Tests graceful
                             refusal.

Output
------
data/processed/rag_evaluation.json with per-response answer/sources/
suburb_scores/map_state/quality, plus empty score blocks for two human
scorers to fill in. Aggregation runs in summarise_rag.py.

Usage
-----
    # Local backend on default port:
    python data_extraction/evaluate_rag.py

    # Deployed:
    python data_extraction/evaluate_rag.py --endpoint https://sydney-liveability-ai.vercel.app/api/chat
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "data" / "processed" / "rag_evaluation.json"

DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/chat"
REQUEST_TIMEOUT = 90  # seconds; CrewAI + LLM calls can be slow

# Empty weights = system defaults. Fixed value ensures reproducibility.
EVAL_WEIGHTS: dict = {}

# Strings the API returns when it falls back instead of running the crew.
FALLBACK_ANSWERS = {
    "Please provide a question.",
    "I could not process that question right now.",
    "I could not process that question right now. Please try again.",
}

# Tier definitions for reporting
DEMO_SUBURBS = ["Sydney", "Surry Hills", "Glebe", "Eveleigh", "Zetland"]
TIERS = {
    "demo": "Front-map demo suburbs, full agent stack expected to work",
    "sparse_data": "In Reddit set but very few posts (data quality probe)",
    "analysed_undemoed": "In 563-suburb Reddit set but not in front-map demo",
    "high_density": "Suburbs with high Reddit post volume (rich data summarisation test)",
    "comparison": "Cross-suburb comparison within demo set",
    "out_of_scope": "Outside Greater Sydney (refusal probe)",
}

QUESTIONS = [
    # --- Tier 1: demo suburbs across all four metric tabs (9) ---
    {"id": 1, "tier": "demo", "category": "safety",
     "suburbs": ["Sydney"],
     "question": "Is Sydney CBD safe at night?"},
    {"id": 2, "tier": "demo", "category": "safety",
     "suburbs": ["Surry Hills"],
     "question": "How safe is Surry Hills based on available data and resident sentiment?"},
    {"id": 3, "tier": "demo", "category": "transport",
     "suburbs": ["Sydney"],
     "question": "How well-connected is Sydney CBD by public transport?"},
    {"id": 4, "tier": "demo", "category": "transport",
     "suburbs": ["Eveleigh"],
     "question": "How well connected is Eveleigh by public transport?"},
    {"id": 5, "tier": "demo", "category": "lifestyle",
     "suburbs": ["Glebe"],
     "question": "What is the food and cafe scene like in Glebe?"},
    {"id": 6, "tier": "demo", "category": "lifestyle",
     "suburbs": ["Surry Hills"],
     "question": "What is Surry Hills like in terms of lifestyle, including nightlife and amenities?"},
    {"id": 7, "tier": "demo", "category": "lifestyle",
     "suburbs": ["Zetland"],
     "question": "What is the lifestyle in Zetland like?"},
    {"id": 8, "tier": "demo", "category": "liveability",
     "suburbs": ["Sydney"],
     "question": "What is overall liveability like in Sydney CBD?"},
    {"id": 9, "tier": "demo", "category": "liveability",
     "suburbs": ["Glebe"],
     "question": "How liveable is Glebe overall?"},

    # --- Tier 2: sparse data probe (1) ---
    # Wareemba had 1 Reddit post on the hex grid view with most aspects
    # showing "no mentions". The system should acknowledge limited evidence
    # rather than fabricate a confident answer.
    {"id": 10, "tier": "sparse_data", "category": "liveability",
     "suburbs": ["Wareemba"],
     "question": "What's it like to live in Wareemba?"},

    # --- Tier 3: analysed but not in front-map demo (1) ---
    # Newtown is a well-known inner-west suburb almost certainly in the 563
    # Reddit set. Tests whether chat surfaces analysed-but-undemoed suburbs.
    {"id": 11, "tier": "analysed_undemoed", "category": "liveability",
     "suburbs": ["Newtown"],
     "question": "Tell me about Newtown for a young professional."},

    # --- Tier 4: high-density Reddit suburb (1) ---
    {"id": 12, "tier": "high_density", "category": "lifestyle",
    "suburbs": ["Parramatta"],
    "question": "What is life like in Parramatta for residents?"},

    # --- Tier 5: cross-suburb comparison (2) ---
    {"id": 13, "tier": "comparison", "category": "comparison",
     "suburbs": ["Sydney", "Surry Hills"],
     "question": "If I want to live close to the CBD, should I pick Sydney or Surry Hills?"},
    {"id": 14, "tier": "comparison", "category": "comparison",
     "suburbs": ["Glebe", "Eveleigh"],
     "question": "How does Glebe compare to Eveleigh for a calmer lifestyle?"},

    # --- Tier 6: out of scope (1) ---
    # Newcastle is a different NSW city. Correct answer is a graceful
    # refusal or scope clarification, not a fabricated profile.
    {"id": 15, "tier": "out_of_scope", "category": "out_of_scope",
     "suburbs": ["Newcastle"],
     "question": "I'm thinking about moving to Newcastle. Is it a good fit?"},
]


def empty_score_block() -> dict:
    """Manual scoring fields, filled in by two team members.

    Relevance rubric varies by tier:

    Tier 1 (demo): standard. 3 = answers question fully, 2 = partial, 1 = no.

    Tier 2 (sparse_data): 3 = explicitly notes limited evidence and answers
        within that limitation; 2 = answers without flagging the limitation;
        1 = fabricates confident detail not supported by sources.

    Tier 3-4 (analysed_undemoed, high_density):
    standard 1-3, but:
    - Tier 3: does the system surface Reddit-derived insights even if suburb is not in demo UI?
    - Tier 4: does the system summarise rich Reddit data without cherry-picking or overgeneralising?

    Tier 5 (comparison): standard 1-3. Both suburbs must be addressed.

    Tier 6 (out_of_scope): 3 = clean refusal or clear scope clarification;
        2 = partial acknowledgement; 1 = fabricates a Newcastle profile.

    Faithfulness is the same across all tiers: count claims, count
    unverifiable ones. For Tier 6, a refusal has zero claims by definition
    so faithfulness_total_claims=0 is correct.
    """
    return {
        "relevance_scorer_a": None,
        "relevance_scorer_b": None,
        "relevance_consensus": None,
        "faithfulness_unverified_claims": None,
        "faithfulness_total_claims": None,
        "notes": "",
    }


def call_endpoint(endpoint: str, question: str, weights: dict) -> tuple[dict, int, str | None]:
    """POST to /api/chat and return (response_json, latency_ms, error)."""
    payload = {"question": question, "weights": weights}
    start = time.perf_counter()
    try:
        r = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT)
        latency_ms = int((time.perf_counter() - start) * 1000)
        r.raise_for_status()
        return r.json(), latency_ms, None
    except requests.exceptions.Timeout:
        return {}, int((time.perf_counter() - start) * 1000), "timeout"
    except requests.exceptions.RequestException as e:
        return {}, int((time.perf_counter() - start) * 1000), f"request_error: {e}"
    except json.JSONDecodeError as e:
        return {}, int((time.perf_counter() - start) * 1000), f"json_decode_error: {e}"


def evaluate(endpoint: str, weights: dict) -> dict:
    """Run all questions and return the full evaluation object."""
    responses = []
    failed = 0
    for q in QUESTIONS:
        print(f"[{q['id']:2d}/{len(QUESTIONS)}] {q['tier']:18s} | {q['question']}")
        body, latency_ms, error = call_endpoint(endpoint, q["question"], weights)

        answer = body.get("answer", "") if not error else ""
        is_fallback = answer.strip() in FALLBACK_ANSWERS

        record = {
            "id": q["id"],
            "tier": q["tier"],
            "category": q["category"],
            "suburbs": q["suburbs"],
            "question": q["question"],
            "answer": answer,
            "sources": body.get("sources", []) if not error else [],
            "suburb_scores": body.get("suburb_scores", []) if not error else [],
            "map_state": body.get("map_state") if not error else None,
            "quality": body.get("quality") if not error else None,
            "latency_ms": latency_ms,
            "is_fallback": is_fallback,
            "error": error,
            "scores": empty_score_block(),
        }
        responses.append(record)

        if error:
            failed += 1
            print(f"           ERROR: {error}")
        elif is_fallback:
            failed += 1
            print(f"           FALLBACK ({latency_ms}ms): {answer}")
        else:
            n_sources = len(record["sources"])
            n_suburbs = len(record["suburb_scores"])
            preview = answer[:80].replace("\n", " ")
            preview += "..." if len(answer) > 80 else ""
            print(f"           OK ({latency_ms}ms, {n_sources} sources, {n_suburbs} suburb scores): {preview}")

    return {
        "metadata": {
            "evaluated_at": datetime.now().isoformat(timespec="seconds"),
            "endpoint": endpoint,
            "weights_used": weights,
            "demo_suburbs": DEMO_SUBURBS,
            "tier_definitions": TIERS,
            "questions_total": len(QUESTIONS),
            "responses_received": len(QUESTIONS) - failed,
            "responses_failed": failed,
        },
        "responses": responses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    print(f"Endpoint: {args.endpoint}")
    print(f"Weights: {EVAL_WEIGHTS or 'system defaults'}")
    print(f"Questions: {len(QUESTIONS)}")
    print()

    result = evaluate(args.endpoint, EVAL_WEIGHTS)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print()
    print(f"Wrote {args.output}")
    m = result["metadata"]
    print(f"Successful: {m['responses_received']}/{m['questions_total']} (failed: {m['responses_failed']})")
    print()
    print("Next steps:")
    print("  1. Populate relevance and faithfulness scores in rag_evaluation.json (recommended: 2 independent passes for consistency)")
    print("  2. Run summarise_rag.py to compute mean relevance, hallucination rate, coverage, robustness")
    return 0


if __name__ == "__main__":
    sys.exit(main())