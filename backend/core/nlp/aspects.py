"""Zero-shot aspect classification for liveability dimensions."""

from __future__ import annotations

from transformers import pipeline

ASPECT_TAXONOMY: dict[str, dict] = {
    "safety": {
        "search_keywords": ["safety", "crime", "safe"],
        "zero_shot_label": "safety and crime",
    },
    "food_and_cafe": {
        "search_keywords": ["cafe", "restaurant", "food"],
        "zero_shot_label": "food, cafes, and restaurants",
    },
    "nightlife": {
        "search_keywords": ["nightlife", "bars", "pub"],
        "zero_shot_label": "nightlife, bars, and entertainment",
    },
    "affordability": {
        "search_keywords": ["rent", "price", "afford"],
        "zero_shot_label": "rent, housing affordability",
    },
    "transport": {
        "search_keywords": ["train", "bus", "transport"],
        "zero_shot_label": "public transport and commuting",
    },
    "community": {
        "search_keywords": ["community", "vibe", "people"],
        "zero_shot_label": "community and neighbourhood vibe",
    },
    "noise": {
        "search_keywords": ["noise", "quiet", "loud"],
        "zero_shot_label": "noise and quiet",
    },
    "green_space": {
        "search_keywords": ["park", "green", "nature"],
        "zero_shot_label": "parks and green spaces",
    },
}

CANDIDATE_LABELS = [v["zero_shot_label"] for v in ASPECT_TAXONOMY.values()]
LABEL_TO_ASPECT = {v["zero_shot_label"]: k for k, v in ASPECT_TAXONOMY.items()}

_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
        )
    return _classifier


def classify_aspects(
    texts: list[str],
    threshold: float = 0.3,
) -> list[dict[str, float]]:
    """Classify texts into liveability aspects using zero-shot classification.

    Args:
        texts: List of text strings to classify.
        threshold: Minimum confidence to assign an aspect.

    Returns:
        List of dicts mapping aspect names to confidence scores.
        Each text can map to multiple aspects (multi-label).
    """
    if not texts:
        return []

    classifier = _get_classifier()
    results = classifier(
        texts,
        candidate_labels=CANDIDATE_LABELS,
        multi_label=True,
    )

    # Single text returns a dict, multiple returns a list
    if isinstance(results, dict):
        results = [results]

    classified = []
    for result in results:
        aspects = {}
        for label, score in zip(result["labels"], result["scores"]):
            if score >= threshold:
                aspect_name = LABEL_TO_ASPECT[label]
                aspects[aspect_name] = score
        classified.append(aspects)

    return classified
