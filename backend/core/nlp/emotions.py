"""Emotion detection using a transformer-based classifier."""

from __future__ import annotations

from transformers import pipeline

EMOTION_LABELS = ["anger", "disgust", "fear", "joy", "sadness", "surprise"]

_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None,
            truncation=True,
        )
    return _classifier


def detect_emotions(texts: list[str]) -> list[dict[str, float]]:
    """Detect emotions for a list of texts.

    Args:
        texts: List of text strings to classify.

    Returns:
        List of dicts mapping emotion labels to probabilities.
    """
    if not texts:
        return []

    classifier = _get_classifier()
    # The model may add a "neutral" label; we keep all labels
    results = classifier(texts)

    parsed = []
    for result in results:
        emotions = {item["label"]: round(item["score"], 4) for item in result}
        parsed.append(emotions)

    return parsed


def aggregate_emotions(emotion_results: list[dict[str, float]]) -> dict[str, float]:
    """Compute suburb-level emotion profile as the mean across all texts.

    Args:
        emotion_results: Output from detect_emotions.

    Returns:
        Dict mapping emotion labels to average probabilities.
    """
    if not emotion_results:
        return {}

    totals: dict[str, float] = {}
    for result in emotion_results:
        for label, score in result.items():
            totals[label] = totals.get(label, 0.0) + score

    count = len(emotion_results)
    return {label: round(total / count, 4) for label, total in totals.items()}
