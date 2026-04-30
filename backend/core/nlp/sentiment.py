"""Aspect-Based Sentiment Analysis using yangheng/deberta-v3-base-absa-v1.1.

Replaces the previous VADER-based scoring. ABSA scores sentiment jointly
with the aspect span on each (text, aspect) pair, so a single post can
register positive food sentiment and negative rent sentiment without the
two cancelling out the way they did under whole-text VADER.
"""

from __future__ import annotations

from .aspects import ASPECT_TAXONOMY

ABSA_MODEL_NAME = "yangheng/deberta-v3-base-absa-v1.1"

# Map ABSA labels to a 0-1 polarity, mirroring the previous VADER scale
# where 0.5 is neutral. Two label conventions are seen in the wild
# depending on transformers version / config:
#   - "Negative" / "Neutral" / "Positive"
#   - "LABEL_0" / "LABEL_1" / "LABEL_2" (= neg/neu/pos)
_LABEL_TO_POLARITY: dict[str, float] = {
    "negative": 0.0,
    "neutral": 0.5,
    "positive": 1.0,
    "label_0": 0.0,
    "label_1": 0.5,
    "label_2": 1.0,
}

# Below this ABSA confidence we route to the BART-MNLI fallback path.
# Calibrated against a small Reddit sample where the model was overconfident
# on very short or out-of-domain comments.
ABSA_CONFIDENCE_THRESHOLD = 0.55

# Posts with fewer words than this are routed through the fallback path
# regardless of ABSA confidence — ABSA is trained on product reviews and
# behaves badly on terse Reddit one-liners.
SHORT_TEXT_WORD_THRESHOLD = 10

# Fallback sentiment contribution is dampened in the aggregate so a corpus
# of short noisy posts does not drown out the signal from longer ABSA-confident
# ones. Applied as a weight multiplier alongside the upvote weight.
FALLBACK_WEIGHT_MULTIPLIER = 0.5

_absa_pipeline = None


def _get_absa_pipeline():
    global _absa_pipeline
    if _absa_pipeline is None:
        from transformers import pipeline

        _absa_pipeline = pipeline(
            "text-classification",
            model=ABSA_MODEL_NAME,
            top_k=None,
            truncation=True,
        )
    return _absa_pipeline


def _polarity_from_absa(scores: list[dict]) -> tuple[float, float]:
    """Convert ABSA per-label scores to (polarity, confidence).

    polarity is in [0, 1] (0.5 neutral); confidence is the max label score.
    """
    weighted = 0.0
    total = 0.0
    best_score = 0.0
    for entry in scores:
        label = str(entry.get("label", "")).strip().lower()
        score = float(entry.get("score", 0.0))
        if label not in _LABEL_TO_POLARITY:
            continue
        weighted += _LABEL_TO_POLARITY[label] * score
        total += score
        if score > best_score:
            best_score = score
    if total <= 0.0:
        return 0.5, 0.0
    return weighted / total, best_score


def _heuristic_polarity(text: str) -> float:
    """Cheap polarity proxy for short / low-confidence posts.

    Tiny lexicon of common Reddit-flavour positive/negative cues. Used only
    in the fallback path — the heavy lifting still goes through ABSA.
    """
    pos = (
        "love", "great", "amazing", "best", "awesome", "fantastic", "lovely",
        "good", "excellent", "perfect", "nice", "happy", "fun", "cool",
        "recommend", "favourite", "favorite",
    )
    neg = (
        "hate", "worst", "awful", "terrible", "bad", "horrible", "rubbish",
        "shit", "shithole", "dodgy", "sketchy", "unsafe", "expensive",
        "overpriced", "noisy", "boring", "dead", "avoid",
    )
    lowered = text.lower()
    p = sum(1 for w in pos if w in lowered)
    n = sum(1 for w in neg if w in lowered)
    if p == n:
        return 0.5
    if p > n:
        return min(1.0, 0.6 + 0.1 * (p - n))
    return max(0.0, 0.4 - 0.1 * (n - p))


def score_aspect_sentiment(text: str, aspect_label: str) -> tuple[float, float, bool]:
    """Score sentiment of `text` with respect to `aspect_label` via ABSA.

    Args:
        text: The post text.
        aspect_label: Human-readable aspect (the zero-shot label from
            ASPECT_TAXONOMY[d]['zero_shot_label']).

    Returns:
        (polarity, confidence, used_fallback) where polarity is in [0, 1],
        confidence is in [0, 1], and used_fallback indicates whether the
        ABSA path was bypassed for the heuristic.
    """
    word_count = len(text.split())
    pipe = _get_absa_pipeline()

    used_fallback = False
    polarity = 0.5
    confidence = 0.0

    if word_count >= SHORT_TEXT_WORD_THRESHOLD:
        try:
            raw = pipe({"text": text, "text_pair": aspect_label})
        except Exception:
            raw = None
        if raw is not None:
            scores = raw if isinstance(raw, list) else [raw]
            if scores and isinstance(scores[0], list):
                scores = scores[0]
            polarity, confidence = _polarity_from_absa(scores)

    if word_count < SHORT_TEXT_WORD_THRESHOLD or confidence < ABSA_CONFIDENCE_THRESHOLD:
        used_fallback = True
        polarity = _heuristic_polarity(text)
        # Confidence in the fallback is intentionally low; the aggregate
        # weight multiplier handles dampening in aggregate_aspect_sentiment.
        confidence = max(confidence, 0.3)

    return polarity, confidence, used_fallback


def aggregate_aspect_sentiment(
    texts: list[str],
    scores: list[int],
    aspect_classifications: list[dict[str, float]],
) -> dict[str, dict]:
    """Compute weighted average ABSA sentiment per aspect.

    Args:
        texts: List of text strings.
        scores: Reddit upvote scores (used as base weights).
        aspect_classifications: Output from classify_aspects — list of
            dicts mapping aspect names to BART-MNLI confidence scores.

    Returns:
        Dict mapping aspect names to {score: float, mentions: int}. Per-aspect
        score is a weight-blended average where weight = upvote * (multiplier
        if fallback else 1.0). Public signature unchanged from the VADER era.
    """
    aspect_totals: dict[str, float] = {}
    aspect_weights: dict[str, float] = {}
    aspect_mentions: dict[str, int] = {}

    for text, upvote_score, aspects in zip(texts, scores, aspect_classifications):
        upvote_weight = max(upvote_score, 1)
        for aspect_name, bart_score in aspects.items():
            aspect_label = ASPECT_TAXONOMY[aspect_name]["zero_shot_label"]
            polarity, _conf, used_fallback = score_aspect_sentiment(
                text, aspect_label
            )

            weight = upvote_weight
            if used_fallback:
                weight = upvote_weight * FALLBACK_WEIGHT_MULTIPLIER

            aspect_totals[aspect_name] = (
                aspect_totals.get(aspect_name, 0.0) + polarity * weight
            )
            aspect_weights[aspect_name] = (
                aspect_weights.get(aspect_name, 0.0) + weight
            )
            aspect_mentions[aspect_name] = (
                aspect_mentions.get(aspect_name, 0) + 1
            )

    result: dict[str, dict] = {}
    for aspect_name, total in aspect_totals.items():
        denom = aspect_weights[aspect_name]
        weighted_avg = total / denom if denom > 0 else 0.5
        result[aspect_name] = {
            "score": round(weighted_avg, 3),
            "mentions": aspect_mentions[aspect_name],
        }

    return result
