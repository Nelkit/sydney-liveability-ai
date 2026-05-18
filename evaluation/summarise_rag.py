"""Compatibility wrapper for embedded RAG evaluation summaries.

The summary logic now lives in evaluate_rag.py so data/eval/rag_evaluation.json
contains both raw responses and UI-ready aggregate metrics.

Usage
-----
    python evaluation/summarise_rag.py
"""

from __future__ import annotations

import json

from evaluate_rag import OUTPUT_FILE, attach_summary, print_summary


def main() -> int:
    if not OUTPUT_FILE.exists():
        print(f"ERROR: {OUTPUT_FILE} not found.")
        print("Run `python evaluation/evaluate_rag.py` first.")
        return 1

    with open(OUTPUT_FILE, encoding="utf-8-sig") as f:
        data = json.load(f)

    data = attach_summary(data)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {OUTPUT_FILE}")
    print()
    print_summary(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
