"""NLP pipeline orchestration for suburb Reddit analysis."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, ".")
from data_extraction.extract_reddit import RedditPost

from .aspects import ASPECT_TAXONOMY, classify_aspects
from .emotions import aggregate_emotions, detect_emotions
from .sentiment import aggregate_aspect_sentiment
from .synthesise import get_synthesiser


@dataclass
class SuburbAnalysis:
    suburb: str
    post_count: int
    fetched_at: str
    aspects: dict[str, dict] = field(default_factory=dict)
    emotions: dict[str, float] = field(default_factory=dict)
    narrative: str = ""
    sources: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "suburb": self.suburb,
            "post_count": self.post_count,
            "fetched_at": self.fetched_at,
            "aspects": self.aspects,
            "emotions": self.emotions,
            "narrative": self.narrative,
            "sources": self.sources,
        }


def _empty_analysis(suburb: str) -> SuburbAnalysis:
    return SuburbAnalysis(
        suburb=suburb,
        post_count=0,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        aspects={
            name: {"score": 0.5, "mentions": 0} for name in ASPECT_TAXONOMY
        },
        emotions={},
        narrative=(
            f"There is not enough Reddit data available for {suburb} "
            "to generate a meaningful analysis at this time."
        ),
        sources=[],
    )


def analyse_suburb(suburb: str, posts: list[RedditPost]) -> SuburbAnalysis:
    """Run the full NLP pipeline on Reddit posts for a suburb.

    Pipeline order:
    1. Aspect classification + emotion detection (parallel)
    2. Per-aspect sentiment (depends on aspect classification)
    3. Synthesis (depends on all above)
    """
    if not posts:
        return _empty_analysis(suburb)

    texts = [p.text for p in posts]
    scores = [p.score for p in posts]

    # Step 1: Aspect classification and emotion detection in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        aspect_future = executor.submit(classify_aspects, texts)
        emotion_future = executor.submit(detect_emotions, texts)

        aspect_classifications = aspect_future.result()
        emotion_results = emotion_future.result()

    # Step 2: Per-aspect sentiment (needs aspect classifications)
    aspects = aggregate_aspect_sentiment(texts, scores, aspect_classifications)

    # Fill in aspects that got zero mentions with neutral scores
    for name in ASPECT_TAXONOMY:
        if name not in aspects:
            aspects[name] = {"score": 0.5, "mentions": 0}

    # Step 3: Aggregate emotions
    emotions = aggregate_emotions(emotion_results)

    # Step 4: Synthesis
    post_dicts = [
        {"text": p.text, "score": p.score, "url": p.url} for p in posts
    ]
    synthesiser = get_synthesiser()
    narrative = synthesiser.synthesise(suburb, post_dicts, aspects, emotions)

    # Build source references (top scored posts)
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
    )
