"""VADER-based per-aspect sentiment scoring."""

from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def score_sentiment(text: str) -> float:
    """Score sentiment of a text on a 0-1 scale.

    VADER's compound score ranges from -1 to +1.
    We normalise to 0-1 where 0.5 is neutral.
    """
    analyzer = _get_analyzer()
    compound = analyzer.polarity_scores(text)["compound"]
    return (compound + 1) / 2


def aggregate_aspect_sentiment(
    texts: list[str],
    scores: list[int],
    aspect_classifications: list[dict[str, float]],
) -> dict[str, dict]:
    """Compute weighted average sentiment per aspect.

    Args:
        texts: List of text strings.
        scores: Reddit upvote scores (used as weights).
        aspect_classifications: Output from classify_aspects — list of
            dicts mapping aspect names to confidence scores.

    Returns:
        Dict mapping aspect names to {score: float, mentions: int}.
        Sentiment score is 0-1 (0.5 = neutral), weighted by upvote score.
    """
    aspect_totals: dict[str, float] = {}
    aspect_weights: dict[str, float] = {}
    aspect_mentions: dict[str, int] = {}

    for text, upvote_score, aspects in zip(texts, scores, aspect_classifications):
        sentiment = score_sentiment(text)
        weight = max(upvote_score, 1)

        for aspect_name in aspects:
            aspect_totals[aspect_name] = (
                aspect_totals.get(aspect_name, 0.0) + sentiment * weight
            )
            aspect_weights[aspect_name] = (
                aspect_weights.get(aspect_name, 0.0) + weight
            )
            aspect_mentions[aspect_name] = (
                aspect_mentions.get(aspect_name, 0) + 1
            )

    result = {}
    for aspect_name in aspect_totals:
        weighted_avg = aspect_totals[aspect_name] / aspect_weights[aspect_name]
        result[aspect_name] = {
            "score": round(weighted_avg, 3),
            "mentions": aspect_mentions[aspect_name],
        }

    return result
