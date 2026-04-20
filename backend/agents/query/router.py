"""Route user questions into query categories with zero-cost keyword rules.

Inputs: question text
Outputs: question, categories, suburbs_mentioned
Owner: backend team
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from crewai import Agent, Task
from crewai.tools import tool
from sqlalchemy import select

from config import get_agent_llm
from db.models import Suburb
from db.postgres import SessionLocal


@lru_cache(maxsize=1)
def _get_supported_suburbs() -> tuple[str, ...]:
    """Return all known suburb names from the database."""
    try:
        with SessionLocal() as session:
            suburbs = session.scalars(select(Suburb.suburb)).all()
    except Exception:
        return ()

    cleaned = sorted(
        {
            str(suburb).strip()
            for suburb in suburbs
            if suburb is not None and str(suburb).strip()
        },
        key=len,
        reverse=True,
    )
    return tuple(cleaned)

RULES: list[tuple[str, tuple[str, ...]]] = [
    ("crime", ("safe", "crime", "dangerous", "robbery", "assault")),
    ("sentiment", ("feel", "vibe", "community", "residents", "sentiment", "opinion")),
    ("gis", ("park", "transport", "facilities", "gym", "cafe", "walk", "amenities")),
    ("comparator", ("vs", "versus", "compare", "difference", "better", "between")),
]


def _extract_suburbs(question: str) -> list[str]:
    """Return detected suburbs using case-insensitive matching against DB suburbs."""
    lowered = question.lower()
    detected: list[str] = []
    for suburb in _get_supported_suburbs():
        pattern = rf"\b{re.escape(suburb.lower())}\b"
        if re.search(pattern, lowered):
            detected.append(suburb)
    return detected


def _detect_categories(question: str) -> list[str]:
    """Apply deterministic keyword rules and return unique ordered categories."""
    lowered = question.lower()
    categories: list[str] = []
    for category, keywords in RULES:
        if any(token in lowered for token in keywords) and category not in categories:
            categories.append(category)
    return categories or ["sentiment", "gis"]


def _route_question_impl(question: str) -> dict[str, Any]:
    """Internal implementation: classify question and extract suburbs."""
    suburbs_mentioned = _extract_suburbs(question)
    categories = _detect_categories(question)
    if categories == ["sentiment", "gis"] and not suburbs_mentioned:
        categories = ["out_of_scope"]
    return {
        "question": question,
        "categories": categories,
        "suburbs_mentioned": suburbs_mentioned,
    }


@tool("route_question")
def route_question(question: str) -> dict[str, Any]:
    """Wrapper tool for CrewAI: route question into categories and suburbs."""
    return _route_question_impl(question)


router_agent = Agent(
    role="Query Router",
    goal="Classify each question and activate only needed specialist agents.",
    backstory="You enforce deterministic routing to avoid unnecessary model calls.",
    llm=get_agent_llm("router"),
    tools=[route_question],
    verbose=True,
)

router_task = Task(
    description="Route one user question into category tags and mentioned suburbs.",
    expected_output="JSON with keys: question, categories, suburbs_mentioned.",
    agent=router_agent,
)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """Isolated test helper used by query crew orchestration."""
    return _route_question_impl(str(input_data.get("question", "")))


if __name__ == "__main__":
    sample = {"question": "Is Redfern safer than Newtown and which has better transport?"}
    print(run(sample))
