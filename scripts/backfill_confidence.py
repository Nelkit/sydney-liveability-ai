"""Backfill confidence and shrunk aspect scores into cached analyses.

Iterates data/processed/reddit_analyses/*.json, computes confidence from
the stored post_count, shrinks every aspect score toward 0.5, preserves
the original under aspects[d].raw_score, and adds top-level `confidence`
and `confidence_tier` fields. Idempotent: re-running uses raw_score when
present, so repeated runs do not double-shrink.

Run from repo root:  python scripts/backfill_confidence.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from core.nlp.confidence import (  # noqa: E402
    compute_confidence,
    confidence_tier,
    shrink_aspects,
)

ANALYSES_DIR = REPO_ROOT / "data" / "processed" / "reddit_analyses"


def backfill_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    post_count = data.get("post_count", 0)
    confidence = compute_confidence(post_count)
    tier = confidence_tier(confidence)

    aspects = data.get("aspects", {}) or {}
    data["aspects"] = shrink_aspects(aspects, confidence)
    data["confidence"] = round(confidence, 3)
    data["confidence_tier"] = tier

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {"suburb": data.get("suburb"), "post_count": post_count,
            "confidence": data["confidence"], "tier": tier}


def main() -> int:
    if not ANALYSES_DIR.exists():
        print(f"No analyses directory at {ANALYSES_DIR}", file=sys.stderr)
        return 1

    files = sorted(ANALYSES_DIR.glob("*.json"))
    if not files:
        print(f"No cached analyses in {ANALYSES_DIR}", file=sys.stderr)
        return 1

    print(f"Backfilling {len(files)} cached analyses...")
    tier_counts = {"high": 0, "medium": 0, "low": 0}
    for path in files:
        result = backfill_file(path)
        tier_counts[result["tier"]] += 1

    total = len(files)
    print(f"Done. {total} files updated.")
    for tier, count in tier_counts.items():
        pct = 100 * count / total
        print(f"  {tier:>6}: {count:>4} ({pct:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
