"""Reddit data extraction for Sydney suburb discourse analysis.

Fetches posts and comments from r/sydney using aspect-targeted search queries
via PRAW. Can be imported as a module or run standalone for bulk extraction.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import praw
from dotenv import load_dotenv

load_dotenv()

ASPECT_SEARCH_KEYWORDS: dict[str, list[str]] = {
    "safety": ["safety", "crime", "safe"],
    "food_and_cafe": ["cafe", "restaurant", "food"],
    "nightlife": ["nightlife", "bars", "pub"],
    "affordability": ["rent", "price", "afford"],
    "transport": ["train", "bus", "transport"],
    "community": ["community", "vibe", "people"],
    "noise": ["noise", "quiet", "loud"],
    "green_space": ["park", "green", "nature"],
}

MIN_SCORE = 2
SUBREDDIT_NAME = "sydney"
DEFAULT_SUBURBS = [
    "Glebe",
    "Haymarket",
    "Newtown",
    "Redfern",
    "Surry Hills",
]


@dataclass
class RedditPost:
    text: str
    suburb: str
    score: int
    created_utc: float
    url: str
    type: str  # "post" or "comment"
    aspect_query: str


def _get_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "sydney-liveability-ai/0.1"),
    )


def _build_query(suburb: str, keyword: str) -> str:
    """Build a search query, quoting multi-word suburbs."""
    if " " in suburb:
        return f'"{suburb}" {keyword}'
    return f"{suburb} {keyword}"


def fetch_suburb_posts(
    suburb: str,
    aspects: dict[str, list[str]] | None = None,
    reddit: praw.Reddit | None = None,
    limit_per_query: int = 50,
) -> list[RedditPost]:
    """Fetch posts and top-level comments for a suburb from r/sydney.

    Executes one search per aspect keyword group, deduplicates results,
    and filters by minimum score.

    Args:
        suburb: Suburb name (e.g. "Surry Hills").
        aspects: Mapping of aspect name to search keywords.
            Defaults to ASPECT_SEARCH_KEYWORDS.
        reddit: Optional PRAW Reddit instance (created if not provided).
        limit_per_query: Max results per search query.

    Returns:
        List of RedditPost objects with score >= MIN_SCORE.
    """
    if aspects is None:
        aspects = ASPECT_SEARCH_KEYWORDS
    if reddit is None:
        reddit = _get_reddit()

    subreddit = reddit.subreddit(SUBREDDIT_NAME)
    seen_ids: set[str] = set()
    results: list[RedditPost] = []

    for aspect_name, keywords in aspects.items():
        for keyword in keywords:
            query = _build_query(suburb, keyword)
            try:
                submissions = subreddit.search(query, limit=limit_per_query)
            except Exception:
                continue

            for submission in submissions:
                # Collect the post itself
                post_id = f"post_{submission.id}"
                if post_id not in seen_ids and submission.score >= MIN_SCORE:
                    seen_ids.add(post_id)
                    title = submission.title or ""
                    selftext = submission.selftext or ""
                    text = f"{title}\n{selftext}".strip() if selftext else title
                    results.append(
                        RedditPost(
                            text=text,
                            suburb=suburb,
                            score=submission.score,
                            created_utc=submission.created_utc,
                            url=f"https://reddit.com{submission.permalink}",
                            type="post",
                            aspect_query=aspect_name,
                        )
                    )

                # Collect top-level comments
                submission.comments.replace_more(limit=0)
                for comment in submission.comments:
                    comment_id = f"comment_{comment.id}"
                    if comment_id not in seen_ids and comment.score >= MIN_SCORE:
                        seen_ids.add(comment_id)
                        results.append(
                            RedditPost(
                                text=comment.body,
                                suburb=suburb,
                                score=comment.score,
                                created_utc=comment.created_utc,
                                url=f"https://reddit.com{comment.permalink}",
                                type="comment",
                                aspect_query=aspect_name,
                            )
                        )

            time.sleep(1)

    return results


def _suburb_slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def bulk_extract(
    suburbs: list[str] | None = None,
    output_dir: str | Path = "data/raw/reddit",
) -> None:
    """Extract Reddit data for multiple suburbs and write JSON files."""
    if suburbs is None:
        suburbs = DEFAULT_SUBURBS

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    reddit = _get_reddit()

    for suburb in suburbs:
        print(f"Fetching: {suburb}")
        posts = fetch_suburb_posts(suburb, reddit=reddit)
        slug = _suburb_slug(suburb)
        filepath = output_path / f"{slug}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(p) for p in posts], f, indent=2, ensure_ascii=False)
        print(f"  → {len(posts)} results written to {filepath}")


if __name__ == "__main__":
    bulk_extract()
