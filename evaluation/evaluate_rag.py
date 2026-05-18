"""
evaluate_rag.py - Sprint 4 RAG evaluation harness.

Lives in: evaluation/
Output:   data/eval/rag_evaluation.json

Runs a fixed set of test questions through the live /api/chat endpoint
and records the full response payload plus embedded summary metrics for
downstream manual scoring or later UI display.

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
    python evaluation/evaluate_rag.py
    python evaluation/evaluate_rag.py --endpoint https://sydney-liveability-ai.vercel.app/api/chat
    EVAL_ENDPOINT=https://sydney-liveability-ai.vercel.app/api/chat python evaluation/evaluate_rag.py
    python evaluation/evaluate_rag.py --summarise-only
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "data" / "eval" / "rag_evaluation.json"

DEFAULT_ENDPOINT = os.environ.get("EVAL_ENDPOINT", "http://127.0.0.1:8000/api/chat")
REQUEST_TIMEOUT = int(os.environ.get("EVAL_REQUEST_TIMEOUT", "240"))

EVAL_WEIGHTS: dict = {}

FALLBACK_ANSWERS = {
    "Please provide a question.",
    "I could not process that question right now.",
    "I could not process that question right now. Please try again.",
}

OUT_OF_SCOPE_PREFIXES = (
    "I specialise in Sydney suburbs",
    "I specialise only in Sydney suburbs",
)
BACKEND_ERROR_PREFIXES = (
    "Error generating response:",
)

DEMO_SUBURBS = ["Sydney", "Surry Hills", "Glebe", "Eveleigh", "Zetland"]
DEMO_TIER = "demo"
ROBUSTNESS_TIERS = {"sparse_data", "analysed_undemoed", "high_density", "out_of_scope"}
COMPARISON_TIER = "comparison"
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

    Relevance rubric by tier (note: responses now use scenario-specific formatting):
      Tier 1 demo:              3=fully answered with bold metrics + bullet list,
                                2=partial answer or missing blockquote closing,
                                1=not answered / fabricated.
      Tier 2 sparse_data:       3=acknowledged limited evidence and answered
                                within that, 2=answered without flagging gap,
                                1=fabricated confident detail.
      Tier 3/4 undemoed/dense:  standard 1-3; note whether system reached
                                beyond front-map suburbs; blockquote appreciated.
      Tier 5 comparison:        3=both suburbs addressed clearly with differentiators,
                                2=partial / weak comparison, 1=missing suburb(s);
                                blockquote closing expected.
      Tier 6 out_of_scope:      3=clean "I specialise in Sydney" refusal,
                                2=partial refusal with some helpfulness,
                                1=fabricates out-of-scope answer; blockquote
                                appreciated for consistency.

    Faithfulness (all tiers):
      Count every factual claim in the answer. Mark any that cannot be
      traced to a returned source as unverified.
      For Tier 6 refusals: total_claims=0 is correct if purely refusing.
    """
    return {
        "relevance_scorer_a": None,
        "relevance_scorer_b": None,
        "relevance_consensus": None,
        "faithfulness_unverified_claims": None,
        "faithfulness_total_claims": None,
        "notes": "",
    }


def detect_scenario(answer: str, suburbs: list[str]) -> str:
    """Infer scenario from answer and suburbs: out_of_scope, comparator, or single."""
    if answer.startswith(OUT_OF_SCOPE_PREFIXES):
        return "out_of_scope"
    if len(suburbs) > 1:
        return "comparator"
    return "single"


def is_backend_error_answer(answer: str) -> bool:
    """Detect graceful HTTP 200 responses that still contain backend failures."""
    return answer.strip().startswith(BACKEND_ERROR_PREFIXES)


def has_markdown_blockquote(answer: str) -> bool:
    """Check if answer contains closing blockquote line (starts with '>') as per new format."""
    return any(line.strip().startswith(">") for line in answer.split("\n"))


def call_endpoint(
    endpoint: str, question: str, weights: dict
) -> tuple[dict, int, str | None]:
    payload = {"question": question, "weights": weights, "include_debug": True}
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


def check_endpoint(endpoint: str) -> None:
    """Verify the chat endpoint is reachable before running the eval."""
    try:
        response = requests.options(endpoint, timeout=min(REQUEST_TIMEOUT, 10))
        if response.status_code >= 500:
            raise RuntimeError(
                f"Endpoint reachable but returned server error {response.status_code}."
            )
        if response.status_code in {404, 400}:
            raise RuntimeError(
                f"Endpoint responded with {response.status_code}; verify the URL is correct."
            )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Unable to reach endpoint {endpoint}: {exc}"
        ) from exc


def evaluate(endpoint: str, weights: dict) -> dict:
    responses = []
    failed = 0
    for q in QUESTIONS:
        print(f"[{q['id']:2d}/{len(QUESTIONS)}] {q['tier']:20s} | {q['question']}")
        body, latency_ms, error = call_endpoint(endpoint, q["question"], weights)

        answer = body.get("answer", "") if not error else ""
        scenario = detect_scenario(answer, q["suburbs"]) if not error else None
        has_blockquote = has_markdown_blockquote(answer) if not error else False
        backend_error = is_backend_error_answer(answer) if not error else False
        error_detail = body.get("error") if not error else None
        unexpected_out_of_scope = (
            scenario == "out_of_scope" and q["tier"] != "out_of_scope"
        )
        record_error = error
        if isinstance(error_detail, dict):
            record_error = (
                f"backend_error_response: {error_detail.get('type', 'error')}: "
                f"{error_detail.get('message', '')}"
            )
        elif backend_error:
            record_error = f"backend_error_response: {answer}"
        elif unexpected_out_of_scope:
            record_error = "unexpected_out_of_scope_response"

        # out_of_scope is a valid response, not a fallback
        is_fallback = (
            answer.strip() in FALLBACK_ANSWERS
            and scenario != "out_of_scope"
        )

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
            "scenario": scenario,
            "has_blockquote": has_blockquote,
            "latency_ms": latency_ms,
            "is_fallback": is_fallback,
            "backend_error": backend_error,
            "unexpected_out_of_scope": unexpected_out_of_scope,
            "error": record_error,
            "error_detail": error_detail,
            "scores": empty_score_block(),
        }
        responses.append(record)

        if record_error:
            failed += 1
            print(f"           ERROR ({latency_ms}ms): {record_error}")
        elif is_fallback:
            failed += 1
            print(f"           FALLBACK ({latency_ms}ms): {answer}")
        elif scenario == "out_of_scope":
            print(f"           OUT_OF_SCOPE ({latency_ms}ms, blockquote={has_blockquote}): {answer[:60]}...")
        else:
            n_src = len(record["sources"])
            n_sub = len(record["suburb_scores"])
            preview = answer[:80].replace("\n", " ")
            preview += "..." if len(answer) > 80 else ""
            print(f"           OK ({latency_ms}ms, {n_src} sources, {n_sub} suburb scores, blockquote={has_blockquote}): {preview}")

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
            "request_timeout_seconds": REQUEST_TIMEOUT,
        },
        "responses": responses,
    }


def consensus_relevance(scores: dict) -> float | None:
    """Return the agreed relevance score, or None when it is not ready."""
    a = scores.get("relevance_scorer_a")
    b = scores.get("relevance_scorer_b")
    consensus = scores.get("relevance_consensus")
    if consensus is not None:
        return float(consensus)
    if a is None or b is None:
        return None
    if abs(a - b) > 1:
        return None
    return (a + b) / 2


def faithfulness_pair(scores: dict) -> tuple[int, int] | None:
    """Return (unverified_claims, total_claims), or None when unscored."""
    unverified = scores.get("faithfulness_unverified_claims")
    total = scores.get("faithfulness_total_claims")
    if unverified is None or total is None:
        return None
    return int(unverified), int(total)


def summarise_group(responses: list[dict]) -> dict:
    """Aggregate one response group into UI-ready metrics."""
    relevance_scores: list[float] = []
    unscored_relevance_ids: list[int] = []
    diverged_relevance_ids: list[int] = []
    unscored_faithfulness_ids: list[int] = []
    total_claims = 0
    unverified_claims = 0
    faithfulness_scored_count = 0
    blockquote_count = 0

    for response in responses:
        scores = response.get("scores") or {}
        rel = consensus_relevance(scores)
        if rel is None:
            a = scores.get("relevance_scorer_a")
            b = scores.get("relevance_scorer_b")
            if a is not None and b is not None and abs(a - b) > 1:
                diverged_relevance_ids.append(response["id"])
            else:
                unscored_relevance_ids.append(response["id"])
        else:
            relevance_scores.append(rel)

        faithfulness = faithfulness_pair(scores)
        if faithfulness is None:
            unscored_faithfulness_ids.append(response["id"])
        else:
            unverified, total = faithfulness
            faithfulness_scored_count += 1
            total_claims += total
            unverified_claims += unverified

        if response.get("has_blockquote"):
            blockquote_count += 1

    verified_claims = max(total_claims - unverified_claims, 0)
    return {
        "count": len(responses),
        "relevance": {
            "scored_count": len(relevance_scores),
            "mean": round(statistics.mean(relevance_scores), 2) if relevance_scores else None,
            "unscored_ids": unscored_relevance_ids,
            "diverged_ids": diverged_relevance_ids,
        },
        "faithfulness": {
            "scored_count": faithfulness_scored_count,
            "total_claims": total_claims,
            "verified_claims": verified_claims,
            "unverified_claims": unverified_claims,
            "hallucination_rate_pct": (
                round(unverified_claims / total_claims * 100, 1)
                if total_claims
                else None
            ),
            "unscored_ids": unscored_faithfulness_ids,
        },
        "formatting": {
            "blockquote_count": blockquote_count,
            "blockquote_pct": (
                round(blockquote_count / len(responses) * 100, 1)
                if responses
                else None
            ),
        },
    }


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def build_summary(data: dict) -> dict:
    """Build embedded summary metrics for rag_evaluation.json."""
    all_responses = data.get("responses") or []
    n_total = len(all_responses)
    fallback_or_error = [
        r for r in all_responses
        if r.get("is_fallback") or r.get("error")
    ]
    scorable = [
        r for r in all_responses
        if not (r.get("is_fallback") or r.get("error"))
    ]

    demo_resp = [r for r in scorable if r.get("tier") == DEMO_TIER]
    robust_resp = [r for r in scorable if r.get("tier") in ROBUSTNESS_TIERS]
    comp_resp = [r for r in scorable if r.get("tier") == COMPARISON_TIER]

    groups = {
        "demo": summarise_group(demo_resp),
        "robustness": summarise_group(robust_resp),
        "comparison": summarise_group(comp_resp),
        "all_scorable": summarise_group(scorable),
    }

    well_cited = set()
    for response in demo_resp:
        scores = response.get("scores") or {}
        rel = consensus_relevance(scores)
        faithfulness = faithfulness_pair(scores)
        if rel is None or faithfulness is None:
            continue
        unverified, _ = faithfulness
        if rel >= 2 and unverified == 0:
            for suburb in response.get("suburbs") or []:
                if suburb in DEMO_SUBURBS:
                    well_cited.add(suburb)

    tier_summaries = {}
    tier_order = [DEMO_TIER, COMPARISON_TIER, *sorted(ROBUSTNESS_TIERS)]
    for tier in tier_order:
        responses = [r for r in scorable if r.get("tier") == tier]
        if not responses:
            continue
        tier_summaries[tier] = {
            "label": (data.get("metadata") or {}).get("tier_definitions", {}).get(tier, tier),
            **summarise_group(responses),
        }

    category_summaries = {}
    for category in sorted({r.get("category", "unknown") for r in scorable}):
        responses = [r for r in scorable if r.get("category", "unknown") == category]
        category_summaries[category] = summarise_group(responses)

    scenario_distribution = {}
    for response in scorable:
        scenario = response.get("scenario") or "unknown"
        scenario_distribution.setdefault(scenario, {"count": 0, "pct": 0.0})
        scenario_distribution[scenario]["count"] += 1
    for scenario in scenario_distribution.values():
        scenario["pct"] = _pct(scenario["count"], len(scorable))

    latencies = [r["latency_ms"] for r in scorable if r.get("latency_ms")]
    latency = {
        "median_ms": int(statistics.median(latencies)) if latencies else None,
        "min_ms": min(latencies) if latencies else None,
        "max_ms": max(latencies) if latencies else None,
    }

    warnings = []
    for group_name, group in groups.items():
        relevance = group["relevance"]
        faithfulness = group["faithfulness"]
        if relevance["unscored_ids"]:
            warnings.append({
                "scope": group_name,
                "kind": "relevance_unscored",
                "ids": relevance["unscored_ids"],
            })
        if relevance["diverged_ids"]:
            warnings.append({
                "scope": group_name,
                "kind": "relevance_diverged",
                "ids": relevance["diverged_ids"],
            })
        if faithfulness["unscored_ids"]:
            warnings.append({
                "scope": group_name,
                "kind": "faithfulness_unscored",
                "ids": faithfulness["unscored_ids"],
            })

    errors = [
        {
            "id": r.get("id"),
            "tier": r.get("tier"),
            "category": r.get("category"),
            "question": r.get("question"),
            "error": r.get("error") or "fallback",
            "latency_ms": r.get("latency_ms"),
        }
        for r in fallback_or_error
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": {
            "questions_total": n_total,
            "responses_received": len(scorable),
            "responses_failed": len(fallback_or_error),
            "completion_rate_pct": _pct(len(scorable), n_total),
            "fallback_or_error_count": len(fallback_or_error),
        },
        "headline": {
            "mean_relevance": groups["demo"]["relevance"]["mean"],
            "hallucination_rate_pct": groups["demo"]["faithfulness"]["hallucination_rate_pct"],
            "blockquote_compliance_pct": groups["demo"]["formatting"]["blockquote_pct"],
            "demo_suburb_coverage_pct": round(len(well_cited) / len(DEMO_SUBURBS) * 100, 1),
            "well_cited_demo_suburbs": sorted(well_cited),
            "missing_demo_suburbs": sorted(set(DEMO_SUBURBS) - well_cited),
            "median_latency_ms": latency["median_ms"],
        },
        "groups": groups,
        "by_tier": tier_summaries,
        "by_category": category_summaries,
        "scenario_distribution": scenario_distribution,
        "latency": latency,
        "errors": errors,
        "warnings": warnings,
    }


def attach_summary(data: dict) -> dict:
    """Return evaluation data with a refreshed embedded summary block."""
    data["schema_version"] = "rag-evaluation-v2"
    data["summary"] = build_summary(data)
    return data


def print_summary(data: dict) -> None:
    """Print a short markdown summary from the embedded JSON metrics."""
    summary = data.get("summary") or {}
    metadata = data.get("metadata") or {}
    status = summary.get("status") or {}
    headline = summary.get("headline") or {}

    print("# RAG Evaluation Summary")
    print()
    print(f"- Evaluated at: {metadata.get('evaluated_at')}")
    print(f"- Endpoint: `{metadata.get('endpoint')}`")
    print(f"- Weights: `{metadata.get('weights_used', {}) or 'system defaults'}`")
    print(
        f"- Questions: {status.get('questions_total', 0)} total "
        f"({status.get('responses_received', 0)} scorable + "
        f"{status.get('responses_failed', 0)} fallback/error)"
    )
    if headline.get("median_latency_ms") is not None:
        print(f"- Median latency: {headline['median_latency_ms']} ms")
    print()

    print("## Headline Metrics")
    print()
    print(f"- Mean relevance (demo): {headline.get('mean_relevance') or 'not yet scored'}")
    hallucination_rate = headline.get("hallucination_rate_pct")
    print(
        "- Hallucination rate (demo): "
        f"{hallucination_rate}%" if hallucination_rate is not None
        else "- Hallucination rate (demo): not yet scored"
    )
    print(
        "- Markdown blockquote compliance (demo): "
        f"{headline.get('blockquote_compliance_pct')}%"
    )
    print(
        "- Demo suburb coverage: "
        f"{headline.get('demo_suburb_coverage_pct')}% "
        f"({len(headline.get('well_cited_demo_suburbs') or [])}/{len(DEMO_SUBURBS)} well-cited)"
    )
    print()

    errors = summary.get("errors") or []
    if errors:
        print(f"## Fallback / Error Responses ({len(errors)})")
        print()
        for error in errors:
            print(f"- Q{error['id']} ({error['tier']}): {error['error']}")
        print()

    for warning in summary.get("warnings") or []:
        print(f"WARNING [{warning['scope']}] {warning['kind']}: ids {warning['ids']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument(
        "--summarise-only",
        action="store_true",
        help="Refresh embedded summary metrics in an existing rag_evaluation.json without calling /api/chat.",
    )
    args = parser.parse_args()

    if args.summarise_only:
        if not args.output.exists():
            print(f"ERROR: {args.output} not found.")
            print("Run `python evaluation/evaluate_rag.py` first.")
            return 1
        with open(args.output, encoding="utf-8-sig") as f:
            result = json.load(f)
        result = attach_summary(result)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Wrote {args.output}")
        print()
        print_summary(result)
        return 0

    print(f"Endpoint: {args.endpoint}")
    print(f"Output:   {args.output}")
    print(f"Weights:  {EVAL_WEIGHTS or 'system defaults'}")
    print(f"Questions: {len(QUESTIONS)}")
    print(f"Timeout:  {REQUEST_TIMEOUT}s per question")
    print()

    try:
        check_endpoint(args.endpoint)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        print("Verify that the server is running and that the endpoint URL is correct.")
        return 1

    result = attach_summary(evaluate(args.endpoint, EVAL_WEIGHTS))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print()
    print(f"Wrote {args.output}")
    m = result["metadata"]
    print(f"Successful: {m['responses_received']}/{m['questions_total']} (failed: {m['responses_failed']})")
    print()
    print_summary(result)
    print()
    print("Next steps:")
    print("  1. Fill relevance + faithfulness scores in data/eval/rag_evaluation.json")
    print("  2. python evaluation/evaluate_rag.py --summarise-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
