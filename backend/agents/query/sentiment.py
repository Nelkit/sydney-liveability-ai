"""Sentiment specialist for aspect and emotion signals.

Inputs: suburb name, optional aspect filter
Outputs: aspect scores, emotion profile, overall sentiment label
Owner: Kai (Ying-Kai Liao)
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Task
from crewai.tools import tool

from config import get_agent_llm


def _query_sentiment_impl(suburb: str, aspect: str | None = None) -> dict[str, Any]:
    """Internal implementation: query sentiment and emotion data."""
    # TODO(Kai): Query tables `sentiment_scores` and `emotion_profiles`.
    # 1) Select all aspect rows for suburb from sentiment_scores.
    # 2) If aspect is provided, filter to that aspect only.
    # 3) Fetch one emotion_profiles row for the suburb.
    # 4) Compute average aspect score and map label:
    #    positive if avg > 0.65, negative if avg < 0.45, else neutral.
    # 5) Return {suburb, aspects, emotions, overall}.
    return {
        "suburb": suburb,
        "aspects": {
            "safety": "pending for implementation",
            "transport": "pending for implementation",
            "amenities": "pending for implementation",
            "community": "pending for implementation",
            "environment": "pending for implementation",
        },
        "emotions": {
            "positive": "pending for implementation",
            "neutral": "pending for implementation",
            "negative": "pending for implementation",
        },
        "overall": "pending for implementation",
        "implementation_status": "Reddit sentiment analysis integration in progress",
    }


@tool("query_sentiment_tool")
def query_sentiment_tool(suburb: str, aspect: str | None = None) -> dict[str, Any]:
    """Wrapper tool for CrewAI: query sentiment data."""
    return _query_sentiment_impl(suburb, aspect)


sentiment_agent = Agent(
    role="Query Sentiment Analyst",
    goal="Explain local sentiment using aspect scores and emotion distributions.",
    backstory="You transform structured sentiment tables into clear suburb-level signals.",
    llm=get_agent_llm("sentiment"),
    tools=[query_sentiment_tool],
    verbose=True,
)

sentiment_task = Task(
    description="Fetch sentiment and emotion evidence for one suburb.",
    expected_output="JSON: {suburb, aspects, emotions, overall}.",
    agent=sentiment_agent,
)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """Isolated execution helper for query crew routing."""
    return _query_sentiment_impl(
        suburb=str(input_data.get("suburb", "")),
        aspect=input_data.get("aspect"),
    )


if __name__ == "__main__":
    print(run({"suburb": "Glebe"}))
