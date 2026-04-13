"""Reddit analysis API endpoint with Supabase caching."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

sys.path.insert(0, ".")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reddit", tags=["reddit"])

CACHE_TTL_HOURS = 24


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


@router.get("/{suburb}")
def analyse_suburb_endpoint(suburb: str) -> dict:
    """Analyse Reddit discourse about a Sydney suburb.

    Returns aspect-based sentiment, emotion profile, community narrative,
    and source references. Results are cached for 24 hours.
    """
    normalised = _normalise_suburb(suburb)

    # Check cache
    supabase = _get_supabase()
    cached = _cache_lookup(supabase, normalised)
    if cached is not None:
        return cached

    # Cache miss: fetch from Reddit and run NLP pipeline
    from data_extraction.extract_reddit import fetch_suburb_posts
    from core.nlp.pipeline import analyse_suburb

    posts = fetch_suburb_posts(normalised)
    result = analyse_suburb(normalised, posts)
    response = result.to_dict()

    # Cache the result
    _cache_write(supabase, response)

    return response
