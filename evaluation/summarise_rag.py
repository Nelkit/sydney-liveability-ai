"""
summarise_rag.py - Aggregate manually-scored RAG evaluation into headline metrics.

Lives in: eval/
Reads:    data/eval/rag_evaluation.json
Writes:   data/eval/rag_summary.json  (machine-readable)
Prints:   markdown summary ready to paste into the report Evaluation section

Run after both scorers have filled in the `scores` blocks in rag_evaluation.json.

Usage
-----
    python eval/summarise_rag.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE  = REPO_ROOT / "data" / "eval" / "rag_evaluation.json"
OUTPUT_JSON = REPO_ROOT / "data" / "eval" / "rag_summary.json"

DEMO_SUBURBS = ["Sydney", "Surry Hills", "Glebe", "Eveleigh", "Zetland"]
DEMO_TIER = "demo"
ROBUSTNESS_TIERS = {"sparse_data", "analysed_undemoed", "high_density", "out_of_scope"}
COMPARISON_TIER = "comparison"


def consensus_relevance(scores: dict) -> float | None:
    a = scores.get("relevance_scorer_a")
    b = scores.get("relevance_scorer_b")
    if a is None or b is None:
        return None
    if abs(a - b) > 1 and scores.get("relevance_consensus") is None:
        return None
    if scores.get("relevance_consensus") is not None:
        return float(scores["relevance_consensus"])
    return (a + b) / 2


def faithfulness_pair(scores: dict) -> tuple[int, int] | None:
    u = scores.get("faithfulness_unverified_claims")
    t = scores.get("faithfulness_total_claims")
    if u is None or t is None:
        return None
    return int(u), int(t)


def summarise_group(responses: list[dict]) -> dict:
    rels, diverged, unscored_rel = [], [], []
    total_claims = unverified_claims = 0
    unscored_faith = []

    for r in responses:
        rel = consensus_relevance(r["scores"])
        if rel is None:
            a = r["scores"].get("relevance_scorer_a")
            b = r["scores"].get("relevance_scorer_b")
            (diverged if (a is not None and b is not None) else unscored_rel).append(r["id"])
        else:
            rels.append(rel)

        f = faithfulness_pair(r["scores"])
        if f is None:
            unscored_faith.append(r["id"])
        else:
            u, t = f
            total_claims += t
            unverified_claims += u

    return {
        "n": len(responses),
        "mean_relevance": round(statistics.mean(rels), 2) if rels else None,
        "total_claims": total_claims,
        "unverified_claims": unverified_claims,
        "hallucination_rate_pct": (
            round(unverified_claims / total_claims * 100, 1) if total_claims else None
        ),
        "unscored_relevance_ids": unscored_rel,
        "diverged_ids": diverged,
        "unscored_faithfulness_ids": unscored_faith,
    }


def main() -> int:
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found.")
        print("Run `python eval/evaluate_rag.py` first.")
        return 1

    with open(INPUT_FILE) as f:
        data = json.load(f)

    all_r = data["responses"]
    n_total = len(all_r)
    fallbacks = [r for r in all_r if r.get("is_fallback") or r.get("error")]
    scorable  = [r for r in all_r if not (r.get("is_fallback") or r.get("error"))]

    demo_resp   = [r for r in scorable if r["tier"] == DEMO_TIER]
    robust_resp = [r for r in scorable if r["tier"] in ROBUSTNESS_TIERS]
    comp_resp   = [r for r in scorable if r["tier"] == COMPARISON_TIER]

    headline   = summarise_group(demo_resp)
    robustness = summarise_group(robust_resp)
    comparison = summarise_group(comp_resp)

    # Demo suburb coverage
    well_cited = set()
    for r in demo_resp:
        rel = consensus_relevance(r["scores"])
        f   = faithfulness_pair(r["scores"])
        if rel is None or f is None:
            continue
        u, _ = f
        if rel >= 2 and u == 0:
            for s in r["suburbs"]:
                if s in DEMO_SUBURBS:
                    well_cited.add(s)
    coverage_pct = round(len(well_cited) / len(DEMO_SUBURBS) * 100, 1)

    # Per-tier mean relevance
    tier_table = {}
    for tier in [DEMO_TIER, COMPARISON_TIER, *sorted(ROBUSTNESS_TIERS)]:
        group = [r for r in scorable if r["tier"] == tier]
        if group:
            tier_table[tier] = summarise_group(group)["mean_relevance"]

    # Per-category mean relevance
    cat_means = {}
    for r in scorable:
        rel = consensus_relevance(r["scores"])
        if rel is not None:
            cat_means.setdefault(r["category"], []).append(rel)
    cat_means = {c: round(statistics.mean(v), 2) for c, v in cat_means.items()}

    # Latency
    latencies = [r["latency_ms"] for r in scorable if r.get("latency_ms")]
    median_latency = int(statistics.median(latencies)) if latencies else None

    # ---- Markdown output ----
    print("# RAG Evaluation Summary")
    print()
    print(f"- Evaluated at: {data['metadata']['evaluated_at']}")
    print(f"- Endpoint: `{data['metadata']['endpoint']}`")
    print(f"- Weights: `{data['metadata'].get('weights_used', {}) or 'system defaults'}`")
    print(f"- Questions: {n_total} total  "
          f"({len(demo_resp)} demo + {len(comp_resp)} comparison + "
          f"{len(robust_resp)} robustness + {len(fallbacks)} fallback/error)")
    if median_latency:
        print(f"- Median latency: {median_latency} ms")
    print()

    print("## Headline metrics (Tier 1: demo suburbs)")
    print()
    if headline["mean_relevance"] is not None:
        print(f"- **Mean relevance score (1-3):** {headline['mean_relevance']}")
    else:
        print("- Mean relevance: not yet scored")
    if headline["hallucination_rate_pct"] is not None:
        print(f"- **Hallucination rate:** {headline['hallucination_rate_pct']}% "
              f"({headline['unverified_claims']}/{headline['total_claims']} unverified claims)")
    else:
        print("- Hallucination rate: not yet scored")
    print(f"- **Demo suburb coverage:** {coverage_pct}% "
          f"({len(well_cited)}/{len(DEMO_SUBURBS)} demo suburbs well-cited)")
    print()

    print("## Robustness across data conditions")
    print()
    tier_defs = data["metadata"].get("tier_definitions", {})
    for tier, mean in tier_table.items():
        if tier == DEMO_TIER:
            continue
        label = tier_defs.get(tier, tier)
        print(f"- **{tier}** (mean relevance: {mean if mean is not None else 'unscored'}): {label}")
    print()

    if cat_means:
        print("## Relevance by question category")
        print()
        for cat, mean in sorted(cat_means.items()):
            print(f"- {cat}: {mean}")
        print()

    if fallbacks:
        print(f"## Fallback / error responses ({len(fallbacks)})")
        print()
        for r in fallbacks:
            print(f"- Q{r['id']} ({r['tier']}): {r.get('error') or 'API fallback'}")
        print()

    for grp_name, grp in [("demo", headline), ("robustness", robustness), ("comparison", comparison)]:
        for ids, label in [
            (grp["unscored_relevance_ids"],   "relevance unscored"),
            (grp["diverged_ids"],             "divergence >1, consensus needed"),
            (grp["unscored_faithfulness_ids"], "faithfulness unscored"),
        ]:
            if ids:
                print(f"WARNING [{grp_name}] {label}: ids {ids}")

    # Machine-readable output
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump({
            "headline": {
                "mean_relevance": headline["mean_relevance"],
                "hallucination_rate_pct": headline["hallucination_rate_pct"],
                "demo_suburb_coverage_pct": coverage_pct,
                "well_cited_demo_suburbs": sorted(well_cited),
                "missing_demo_suburbs": sorted(set(DEMO_SUBURBS) - well_cited),
            },
            "by_tier": tier_table,
            "by_category": cat_means,
            "comparison": comparison,
            "robustness": robustness,
            "median_latency_ms": median_latency,
            "n_total": n_total,
            "n_fallback": len(fallbacks),
        }, f, indent=2)

    print()
    print(f"Wrote {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())