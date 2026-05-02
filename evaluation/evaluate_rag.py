"""
evaluate_rag.py - Sprint 4 RAG evaluation harness.

Lives in: eval/
Output:   data/eval/rag_evaluation.json

Runs a fixed set of test questions through the live /api/chat endpoint
and records the full response payload for downstream manual scoring.

Question design
---------------
15 questions across 6 coverage tiers:

  Tier 1  demo             (9): Sydney/Surry Hills/Glebe/Eveleigh/Zetland
                               across safety/transport/lifestyle/liveability.
  Tier 2  sparse_data      (1): Wareemba (1 Reddit post). Tests honest
                               degradation vs fabrication on thin data.
  Tier 3  analysed_undemoed(1): Newtown. In 563-suburb Reddit set but not
                               in the front-map 5. Tests breadth.
  Tier 4  high_density     (1): Parramatta. Rich Reddit data summarisation.
  Tier 5  comparison       (2): Cross-suburb reasoning within demo set.
  Tier 6  out_of_scope     (1): Newcastle. Refusal probe.

Usage
-----
    python eval/evaluate_rag.py
    python eval/evaluate_rag.py --endpoint https://sydney-liveability-ai.vercel.app/api/chat
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
OUTPUT_FILE = REPO_ROOT / "data" / "eval" / "rag_evaluation.json"

DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/chat"
REQUEST_TIMEOUT = 90

EVAL_WEIGHTS: dict = {}

FALLBACK_ANSWERS = {
    "Please provide a question.",
    "I could not process that question right now.",
    "I could not process that question right now. Please try again.",
}

DEMO_SUBURBS = ["Sydney", "Surry Hills", "Glebe", "Eveleigh", "Zetland"]
TIERS = {
    "demo":               "Front-map demo suburbs, full agent stack expected",
    "sparse_data":        "In Reddit set but very few posts (data quality probe)",
    "analysed_undemoed":  "In 563-suburb Reddit set but not in front-map demo",
    "high_density":       "High Reddit post volume (rich data summarisation test)",
    "comparison":         "Cross-suburb comparison within demo set",
    "out_of_scope":       "Outside Greater Sydney (refusal probe)",
}

QUESTIONS = [
    # --- Tier 1: demo suburbs across all four metric tabs (9) ---
    {"id": 1,  "tier": "demo",               "category": "safety",
     "suburbs": ["Sydney"],
     "question": "Is Sydney CBD safe at night?"},
    {"id": 2,  "tier": "demo",               "category": "safety",
     "suburbs": ["Surry Hills"],
     "question": "How safe is Surry Hills based on available data and resident sentiment?"},
    {"id": 3,  "tier": "demo",               "category": "transport",
     "suburbs": ["Sydney"],
     "question": "How well-connected is Sydney CBD by public transport?"},
    {"id": 4,  "tier": "demo",               "category": "transport",
     "suburbs": ["Eveleigh"],
     "question": "How well connected is Eveleigh by public transport?"},
    {"id": 5,  "tier": "demo",               "category": "lifestyle",
     "suburbs": ["Glebe"],
     "question": "What is the food and cafe scene like in Glebe?"},
    {"id": 6,  "tier": "demo",               "category": "lifestyle",
     "suburbs": ["Surry Hills"],
     "question": "What is Surry Hills like in terms of lifestyle, including nightlife and amenities?"},
    {"id": 7,  "tier": "demo",               "category": "lifestyle",
     "suburbs": ["Zetland"],
     "question": "What is the lifestyle in Zetland like?"},
    {"id": 8,  "tier": "demo",               "category": "liveability",
     "suburbs": ["Sydney"],
     "question": "What is overall liveability like in Sydney CBD?"},
    {"id": 9,  "tier": "demo",               "category": "liveability",
     "suburbs": ["Glebe"],
     "question": "How liveable is Glebe overall?"},

    # --- Tier 2: sparse data probe (1) ---
    {"id": 10, "tier": "sparse_data",        "category": "liveability",
     "suburbs": ["Wareemba"],
     "question": "What's it like to live in Wareemba?"},

    # --- Tier 3: analysed but not in front-map demo (1) ---
    {"id": 11, "tier": "analysed_undemoed",  "category": "liveability",
     "suburbs": ["Newtown"],
     "question": "Tell me about Newtown for a young professional."},

    # --- Tier 4: high-density Reddit suburb (1) ---
    {"id": 12, "tier": "high_density",       "category": "lifestyle",
     "suburbs": ["Parramatta"],
     "question": "What is life like in Parramatta for residents?"},

    # --- Tier 5: cross-suburb comparison (2) ---
    {"id": 13, "tier": "comparison",         "category": "comparison",
     "suburbs": ["Sydney", "Surry Hills"],
     "question": "If I want to live close to the CBD, should I pick Sydney or Surry Hills?"},
    {"id": 14, "tier": "comparison",         "category": "comparison",
     "suburbs": ["Glebe", "Eveleigh"],
     "question": "How does Glebe compare to Eveleigh for a calmer lifestyle?"},

    # --- Tier 6: out of scope (1) ---
    {"id": 15, "tier": "out_of_scope",       "category": "out_of_scope",
     "suburbs": ["Newcastle"],
     "question": "I'm thinking about moving to Newcastle. Is it a good fit?"},
]


def empty_score_block() -> dict:
    """Manual scoring fields filled in by two team members.

    Relevance rubric by tier:
      Tier 1 demo:              3=fully answered, 2=partial, 1=not answered.
      Tier 2 sparse_data:       3=acknowledged limited evidence and answered
                                within that, 2=answered without flagging gap,
                                1=fabricated confident detail.
      Tier 3/4 undemoed/dense:  standard 1-3; note whether system reached
                                beyond front-map suburbs.
      Tier 5 comparison:        standard 1-3; both suburbs must be addressed.
      Tier 6 out_of_scope:      3=clean refusal, 2=partial, 1=fabricates.

    Faithfulness (all tiers):
      Count every factual claim in the answer. Mark any that cannot be
      traced to a returned source as unverified.
      For Tier 6 refusals: total_claims=0 is correct.
    """
    return {
        "relevance_scorer_a": None,
        "relevance_scorer_b": None,
        "relevance_consensus": None,
        "faithfulness_unverified_claims": None,
        "faithfulness_total_claims": None,
        "notes": "",
    }


def call_endpoint(
    endpoint: str, question: str, weights: dict
) -> tuple[dict, int, str | None]:
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
    responses = []
    failed = 0
    for q in QUESTIONS:
        print(f"[{q['id']:2d}/{len(QUESTIONS)}] {q['tier']:20s} | {q['question']}")
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
            n_src = len(record["sources"])
            n_sub = len(record["suburb_scores"])
            preview = answer[:80].replace("\n", " ")
            preview += "..." if len(answer) > 80 else ""
            print(f"           OK ({latency_ms}ms, {n_src} sources, {n_sub} suburb scores): {preview}")

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
    print(f"Output:   {args.output}")
    print(f"Weights:  {EVAL_WEIGHTS or 'system defaults'}")
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
    print("  1. Fill relevance + faithfulness scores in data/eval/rag_evaluation.json")
    print("  2. python eval/summarise_rag.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())