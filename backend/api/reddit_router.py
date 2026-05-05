"""Reddit analysis API endpoint — reads structured data from PostgreSQL."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import select

# Ensure repo-root packages (e.g., data_extraction) are importable when
# backend is started from backend/ as the working directory.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db.models import EmotionProfile, SentimentScore, SuburbNarrative
from db.postgres import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reddit", tags=["reddit"])

CACHE_TTL_HOURS = 24
REDDIT_PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "reddit"


def _normalise_suburb(raw: str) -> str:
    """Normalise suburb input to title case for display and search.

    Accepts any casing, underscores, or hyphens.
    """
    cleaned = raw.replace("_", " ").replace("-", " ")
    return cleaned.title()


def _get_supabase():
    """Get Supabase client, or None if unavailable."""
    try:
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        logger.warning("Supabase unavailable, proceeding without cache")
        return None


def _cache_lookup(supabase, suburb: str) -> dict | None:
    """Check Supabase for a cached analysis within the TTL."""
    if supabase is None:
        return None
    try:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
        ).isoformat()
        result = (
            supabase.table("reddit_analyses")
            .select("*")
            .eq("suburb", suburb)
            .gte("fetched_at", cutoff)
            .order("fetched_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            return {
                "suburb": row["suburb"],
                "post_count": row["post_count"],
                "fetched_at": row["fetched_at"],
                "aspects": row["aspects"],
                "emotions": row["emotions"],
                "narrative": row["narrative"],
                "sources": row["sources"],
            }
    except Exception:
        logger.warning("Cache lookup failed, proceeding without cache")
    return None


def _cache_write(supabase, analysis: dict) -> None:
    """Write analysis result to Supabase cache."""
    if supabase is None:
        return
    try:
        supabase.table("reddit_analyses").insert(
            {
                "suburb": analysis["suburb"],
                "post_count": analysis["post_count"],
                "fetched_at": analysis["fetched_at"],
                "aspects": analysis["aspects"],
                "emotions": analysis["emotions"],
                "narrative": analysis["narrative"],
                "sources": analysis["sources"],
            }
        ).execute()
    except Exception:
        logger.warning("Cache write failed, result not cached")


def _pg_lookup(suburb: str) -> dict | None:
    """Read structured sentiment analysis for a suburb from PostgreSQL."""
    try:
        with SessionLocal() as session:
            emotion = session.get(EmotionProfile, suburb)
            if emotion is None:
                return None
            aspect_rows = session.scalars(
                select(SentimentScore).where(SentimentScore.suburb == suburb)
            ).all()
            narrative_row = session.get(SuburbNarrative, suburb)

        return {
            "suburb": suburb,
            "post_count": emotion.post_count,
            "fetched_at": emotion.fetched_at.isoformat() if emotion.fetched_at else None,
            "aspects": {
                row.aspect: {
                    "score": row.score,
                    "mentions": row.mentions,
                    "confidence": row.confidence,
                    "coverage": row.coverage,
                    "source": row.source,
                }
                for row in aspect_rows
            },
            "emotions": {
                "joy": emotion.joy,
                "surprise": emotion.surprise,
                "neutral": emotion.neutral,
                "sadness": emotion.sadness,
                "anger": emotion.anger,
                "fear": emotion.fear,
                "disgust": emotion.disgust,
            },
            "narrative": narrative_row.narrative if narrative_row else None,
            "sources": narrative_row.sources if narrative_row else [],
            "confidence": emotion.confidence,
            "confidence_tier": emotion.confidence_tier,
        }
    except Exception:
        logger.warning("PostgreSQL lookup failed for %s", suburb)
        return None


def _pg_write(analysis: dict) -> None:
    """Upsert a freshly-computed analysis into PostgreSQL."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    suburb = analysis.get("suburb")
    if not suburb:
        return
    try:
        aspects = analysis.get("aspects") or {}
        emotions = analysis.get("emotions") or {}

        aspect_rows = [
            {
                "suburb": suburb,
                "aspect": aspect_name,
                "score": entry.get("score"),
                "mentions": entry.get("mentions"),
                "confidence": entry.get("confidence"),
                "coverage": entry.get("coverage"),
                "source": entry.get("source"),
            }
            for aspect_name, entry in aspects.items()
            if isinstance(entry, dict)
        ]

        fetched_raw = analysis.get("fetched_at")
        fetched_at: datetime | None = None
        if fetched_raw:
            try:
                fetched_at = datetime.fromisoformat(fetched_raw).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        emotion_row = {
            "suburb": suburb,
            "joy": emotions.get("joy"),
            "surprise": emotions.get("surprise"),
            "neutral": emotions.get("neutral"),
            "sadness": emotions.get("sadness"),
            "anger": emotions.get("anger"),
            "fear": emotions.get("fear"),
            "disgust": emotions.get("disgust"),
            "post_count": analysis.get("post_count"),
            "fetched_at": fetched_at,
            "confidence": analysis.get("confidence"),
            "confidence_tier": analysis.get("confidence_tier"),
        }

        narrative_row = {
            "suburb": suburb,
            "narrative": analysis.get("narrative"),
            "sources": analysis.get("sources"),
        }

        with SessionLocal() as session:
            if aspect_rows:
                stmt = pg_insert(SentimentScore.__table__).values(aspect_rows)
                session.execute(stmt.on_conflict_do_update(
                    index_elements=["suburb", "aspect"],
                    set_={c: stmt.excluded[c] for c in ["score", "mentions", "confidence", "coverage", "source"]},
                ))
            stmt = pg_insert(EmotionProfile.__table__).values([emotion_row])
            session.execute(stmt.on_conflict_do_update(
                index_elements=["suburb"],
                set_={c: stmt.excluded[c] for c in [
                    "joy", "surprise", "neutral", "sadness", "anger", "fear", "disgust",
                    "post_count", "fetched_at", "confidence", "confidence_tier",
                ]},
            ))
            stmt = pg_insert(SuburbNarrative.__table__).values([narrative_row])
            session.execute(stmt.on_conflict_do_update(
                index_elements=["suburb"],
                set_={c: stmt.excluded[c] for c in ["narrative", "sources"]},
            ))
            session.commit()
    except Exception:
        logger.warning("PostgreSQL write failed for %s", suburb)


@router.get(
    "/suburbs",
    summary="List suburbs with Reddit data",
    response_description="Sorted list of suburb names that have at least one Reddit post ingested.",
)
def list_suburbs() -> dict:
    """Return all suburb names for which Reddit data has been ingested.

    Useful for populating autocomplete widgets or validating suburb names
    before calling `GET /api/reddit/{suburb}`.

    **Response**
    ```json
    { "suburbs": ["Bondi", "Glebe", "Newtown", ...], "count": 657 }
    ```
    """
    from data_extraction.extract_reddit import list_available_suburbs

    suburbs = list_available_suburbs()
    return {"suburbs": suburbs, "count": len(suburbs)}


@router.get(
    "/summary",
    summary="Suburb sentiment summary (bulk)",
    response_description=(
        "Array of per-suburb summary rows. Cached suburbs include a composite score "
        "and aspect breakdown; uncached suburbs return `score=null`."
    ),
)
def summary() -> dict:
    """Return a lightweight sentiment summary for every suburb that has data.

    Designed for the **hexagon overview page** — fetches all ~657 suburbs in
    a single request rather than making one call per suburb.

    Each row contains:
    - `suburb` — name
    - `post_count` — number of Reddit posts analysed
    - `score` — composite liveability sentiment score (mean of 8 aspect scores, 0–1), or `null`
    - `top_aspect` / `bottom_aspect` — highest/lowest-scoring liveability dimension
    - `dominant_emotion` — most common GoEmotions label across posts
    - `cached` — whether a full NLP analysis is available
    - `confidence` / `confidence_tier` — model confidence (`low | medium | high`)

    **Response**
    ```json
    {
      "suburbs": [
        {
          "suburb": "Newtown",
          "post_count": 312,
          "score": 0.673,
          "top_aspect": "community",
          "bottom_aspect": "affordability",
          "dominant_emotion": "joy",
          "cached": true,
          "confidence": 0.81,
          "confidence_tier": "high"
        }
      ],
      "count": 657
    }
    ```
    """
    from data_extraction.extract_reddit import list_available_suburbs

    suburbs = list_available_suburbs()

    # Load suburb index for raw post counts (includes suburbs without
    # a cached NLP analysis).
    index_path = REDDIT_PROCESSED_DIR / "_suburb_index.json"
    raw_counts: dict[str, int] = {}
    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
            raw_counts = {k: v.get("post_count", 0) for k, v in index.items()}
        except Exception:
            logger.warning("Suburb index read failed")

    rows: list[dict] = []
    for suburb in suburbs:
        cached = _pg_lookup(suburb)
        if cached is not None:
            aspects = cached.get("aspects", {}) or {}
            # Composite score = mean over dims with a non-null score (Reddit-
            # attested or cross-modal-fallback). Null dims are dropped — this
            # is the wire-format contract from the deepen-reddit-transformer
            # change.
            scored = [
                v.get("score")
                for v in aspects.values()
                if v.get("score") is not None
            ]
            if scored:
                composite = round(sum(scored) / len(scored), 3)
            else:
                composite = None

            ranked = [
                (k, v.get("score"))
                for k, v in aspects.items()
                if v.get("score") is not None
            ]
            if ranked:
                ranked.sort(key=lambda pair: pair[1], reverse=True)
                top_aspect = ranked[0][0]
                bottom_aspect = ranked[-1][0]
            else:
                top_aspect = None
                bottom_aspect = None

            emotions = cached.get("emotions", {}) or {}
            dominant = None
            if emotions:
                dominant = max(emotions.items(), key=lambda pair: pair[1])[0]

            rows.append(
                {
                    "suburb": suburb,
                    "post_count": cached.get("post_count", 0),
                    "score": composite,
                    "top_aspect": top_aspect,
                    "bottom_aspect": bottom_aspect,
                    "dominant_emotion": dominant,
                    "cached": True,
                    "confidence": cached.get("confidence", 0.0),
                    "confidence_tier": cached.get("confidence_tier", "low"),
                }
            )
        else:
            rows.append(
                {
                    "suburb": suburb,
                    "post_count": raw_counts.get(suburb, 0),
                    "score": None,
                    "top_aspect": None,
                    "bottom_aspect": None,
                    "dominant_emotion": None,
                    "cached": False,
                    "confidence": 0.0,
                    "confidence_tier": "low",
                }
            )

    return {"suburbs": rows, "count": len(rows)}


@router.get(
    "/{suburb}",
    summary="Suburb Reddit analysis",
    response_description=(
        "Full NLP analysis for the suburb: aspect sentiment scores, GoEmotions profile, "
        "community narrative, and Reddit source URLs."
    ),
    responses={
        200: {
            "description": "Analysis returned from PostgreSQL cache or computed on demand.",
        }
    },
)
def analyse_suburb_endpoint(suburb: str) -> dict:
    """Return the full Reddit NLP analysis for a single Sydney suburb.

    **Cache strategy** (fastest → slowest):
    1. PostgreSQL (primary cache — pre-computed at ingestion time)
    2. Supabase (secondary cache — 24 h TTL)
    3. On-demand: loads raw Reddit posts and runs the full NLP pipeline

    Suburb names are normalised to title case (`newtown` → `Newtown`).
    Underscores and hyphens are replaced with spaces.

    **Aspect dimensions** (DeBERTa-v3 fine-tuned on liveability corpus):
    `safety`, `food_and_cafe`, `nightlife`, `affordability`, `transport`,
    `community`, `noise`, `green_space`

    **Emotion labels** (GoEmotions, averaged across posts):
    `joy`, `surprise`, `neutral`, `sadness`, `anger`, `fear`, `disgust`

    **Response**
    ```json
    {
      "suburb": "Newtown",
      "post_count": 312,
      "fetched_at": "2025-03-01T10:00:00",
      "aspects": {
        "community": { "score": 0.82, "mentions": 47, "confidence": 0.91, "coverage": "strong", "source": "reddit" },
        "affordability": { "score": 0.31, "mentions": 28, "confidence": 0.79, "coverage": "moderate", "source": "reddit" }
      },
      "emotions": { "joy": 0.41, "neutral": 0.29, "sadness": 0.12, "anger": 0.08, "surprise": 0.05, "fear": 0.03, "disgust": 0.02 },
      "narrative": "Newtown residents celebrate the suburb's vibrant arts scene...",
      "sources": ["https://reddit.com/r/sydney/comments/abc123", ...],
      "confidence": 0.81,
      "confidence_tier": "high"
    }
    ```
    """
    normalised = _normalise_suburb(suburb)

    # 1. Check PostgreSQL (primary source of truth)
    pg_cached = _pg_lookup(normalised)
    if pg_cached is not None:
        return pg_cached

    # 2. Check Supabase cache
    supabase = _get_supabase()
    cached = _cache_lookup(supabase, normalised)
    if cached is not None:
        _pg_write(cached)
        return cached

    # 3. Cache miss: load from pre-processed local data and run NLP pipeline
    from data_extraction.extract_reddit import load_suburb_posts
    from core.nlp.pipeline import analyse_suburb

    posts = load_suburb_posts(normalised)
    result = analyse_suburb(normalised, posts)
    response = result.to_dict()

    # Persist result to PostgreSQL and optional Supabase
    _pg_write(response)
    _cache_write(supabase, response)

    return response
