"""NLP pipeline orchestration for suburb Reddit analysis."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, TypedDict

sys.path.insert(0, ".")
from data_extraction.extract_reddit import RedditPost

from .aspects import ASPECT_TAXONOMY, classify_aspects
from .confidence import (
    compute_confidence,
    compute_per_dimension_confidence,
    confidence_tier,
)
from .coverage import compute_coverage
from .emotions import aggregate_emotions, detect_emotions
from .fallback import FALLBACK_POLICY
from .sentiment import aggregate_aspect_sentiment
from .synthesise import get_synthesiser


class AspectEntry(TypedDict):
    """Per-dimension entry in `SuburbAnalysis.aspects`.

    `score` is `None` when the dimension has no Reddit signal AND no
    cross-modal proxy. Downstream consumers MUST treat null as
    missing-data, not as a numeric value.
    """

    score: Optional[float]
    mentions: int
    confidence: float
    coverage: str  # "none" | "weak" | "strong"
    source: str  # "reddit" | "bocsar" | "osm" | "arcgis" | "none"


def _empty_aspect_entry() -> AspectEntry:
    return {
        "score": None,
        "mentions": 0,
        "confidence": 0.0,
        "coverage": "none",
        "source": "none",
    }


@dataclass
class SuburbAnalysis:
    suburb: str
    post_count: int
    fetched_at: str
    aspects: dict[str, AspectEntry] = field(default_factory=dict)
    emotions: dict[str, float] = field(default_factory=dict)
    narrative: str = ""
    sources: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    confidence_tier: str = "low"

    def to_dict(self) -> dict:
        return {
            "suburb": self.suburb,
            "post_count": self.post_count,
            "fetched_at": self.fetched_at,
            "aspects": self.aspects,
            "emotions": self.emotions,
            "narrative": self.narrative,
            "sources": self.sources,
            "confidence": self.confidence,
            "confidence_tier": self.confidence_tier,
        }


def _empty_analysis(suburb: str) -> SuburbAnalysis:
    """Build an analysis for a suburb with no Reddit posts.

    Cross-modal fallbacks are still applied so dimensions like safety/food
    surface a score from BOCSAR/OSM even when the suburb is Reddit-silent.
    """
    aspects: dict[str, dict] = {}
    for name in ASPECT_TAXONOMY:
        aspects[name] = _apply_fallback(suburb, name)

    return SuburbAnalysis(
        suburb=suburb,
        post_count=0,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        aspects=aspects,
        emotions={},
        narrative=(
            f"There is not enough Reddit data available for {suburb} "
            "to generate a meaningful analysis at this time."
        ),
        sources=[],
        confidence=0.0,
        confidence_tier="low",
    )


def _apply_fallback(suburb: str, aspect_name: str) -> dict:
    """Resolve a Reddit-silent dimension via FALLBACK_POLICY or null."""
    handler = FALLBACK_POLICY.get(aspect_name)
    if handler is None:
        return _empty_aspect_entry()
    try:
        out = handler(suburb)
    except KeyError:
        return _empty_aspect_entry()
    return {
        "score": out["score"],
        "mentions": 0,
        "confidence": out["confidence"],
        "coverage": out["coverage_tier"],
        "source": out["source"],
    }


def analyse_suburb(suburb: str, posts: list[RedditPost]) -> SuburbAnalysis:
    """Run the full NLP pipeline on Reddit posts for a suburb.

    Pipeline order:
    1. Aspect classification + emotion detection + coverage detection (parallel)
    2. Per-aspect ABSA sentiment (depends on aspect classification)
    3. Cross-modal fallback for dims with coverage == none
    4. Synthesis (depends on all above)
    """
    if not posts:
        return _empty_analysis(suburb)

    texts = [p.text for p in posts]
    scores = [p.score for p in posts]

    # Step 1: parallel aspect classification, emotion detection, coverage
    with ThreadPoolExecutor(max_workers=3) as executor:
        aspect_future = executor.submit(classify_aspects, texts)
        emotion_future = executor.submit(detect_emotions, texts)
        coverage_future = executor.submit(compute_coverage, texts)

        aspect_classifications = aspect_future.result()
        emotion_results = emotion_future.result()
        coverage = coverage_future.result()

    # Step 2: per-aspect ABSA sentiment (only for dims with non-none coverage)
    reddit_aspects = aggregate_aspect_sentiment(
        texts, scores, aspect_classifications
    )

    # Step 3: build the per-dimension entry, falling back when Reddit is silent
    aspects: dict[str, dict] = {}
    for name in ASPECT_TAXONOMY:
        cov = coverage.get(name, {})
        cov_tier = cov.get("tier", "none")

        if cov_tier == "none":
            aspects[name] = _apply_fallback(suburb, name)
            continue

        reddit_entry = reddit_aspects.get(name)
        if reddit_entry is None:
            # Coverage says the dimension is talked about, but ABSA didn't
            # attribute any specific mentions — treat the dim as Reddit-attested
            # neutral with low confidence rather than silently fall back to GIS.
            aspects[name] = {
                "score": 0.5,
                "mentions": 0,
                "confidence": 0.0,
                "coverage": cov_tier,
                "source": "reddit",
            }
            continue

        mentions = reddit_entry.get("mentions", 0)
        aspects[name] = {
            "score": reddit_entry.get("score", 0.5),
            "mentions": mentions,
            "confidence": round(compute_per_dimension_confidence(mentions), 3),
            "coverage": cov_tier,
            "source": "reddit",
        }

    # Step 4: legacy global confidence (kept for backwards compatibility)
    global_confidence = compute_confidence(len(posts))
    tier = confidence_tier(global_confidence)

    # Step 5: aggregate emotions
    emotions = aggregate_emotions(emotion_results)

    # Step 6: synthesis
    post_dicts = [
        {"text": p.text, "score": p.score, "url": p.url} for p in posts
    ]
    synthesiser = get_synthesiser()
    narrative = synthesiser.synthesise(suburb, post_dicts, aspects, emotions)

    top_posts = sorted(posts, key=lambda p: p.score, reverse=True)[:10]
    sources = [
        {"text": p.text[:200], "url": p.url, "score": p.score}
        for p in top_posts
    ]

    return SuburbAnalysis(
        suburb=suburb,
        post_count=len(posts),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        aspects=aspects,
        emotions=emotions,
        narrative=narrative,
        sources=sources,
        confidence=round(global_confidence, 3),
        confidence_tier=tier,
    )
