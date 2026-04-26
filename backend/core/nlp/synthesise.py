"""Community narrative synthesis — mock and Claude implementations."""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage


@runtime_checkable
class Synthesiser(Protocol):
    def synthesise(
        self,
        suburb: str,
        posts: list[dict],
        aspects: dict[str, dict],
        emotions: dict[str, float],
    ) -> str: ...


class MockSynthesiser:
    """Template-based narrative using real aspect scores."""

    def synthesise(
        self,
        suburb: str,
        posts: list[dict],
        aspects: dict[str, dict],
        emotions: dict[str, float],
    ) -> str:
        if not aspects:
            return (
                f"There is not enough Reddit data available for {suburb} "
                "to generate a community narrative at this time."
            )

        sorted_aspects = sorted(
            aspects.items(), key=lambda x: x[1]["score"], reverse=True
        )
        top = sorted_aspects[:2]
        bottom = sorted_aspects[-2:]

        top_str = " and ".join(
            f"{name.replace('_', ' ')} ({info['score']:.2f})"
            for name, info in top
        )
        bottom_str = " and ".join(
            f"{name.replace('_', ' ')} ({info['score']:.2f})"
            for name, info in bottom
        )

        top_emotion = ""
        if emotions:
            dominant = max(emotions, key=emotions.get)
            top_emotion = f" The dominant emotion in community discussions is {dominant}."

        return (
            f"Reddit discussions about {suburb} are most positive about "
            f"{top_str}. Residents are most critical about {bottom_str}. "
            f"This analysis is based on {len(posts)} posts and comments."
            f"{top_emotion}"
        )


class ClaudeSynthesiser:
    """Claude-powered narrative synthesis via LangChain."""

    def __init__(self):
        self._llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )

    def synthesise(
        self,
        suburb: str,
        posts: list[dict],
        aspects: dict[str, dict],
        emotions: dict[str, float],
    ) -> str:
        sample_texts = [p["text"][:200] for p in posts[:30]]
        texts_block = "\n---\n".join(sample_texts)

        aspects_block = "\n".join(
            f"- {name}: sentiment {info['score']:.2f} ({info['mentions']} mentions)"
            for name, info in aspects.items()
        )

        emotions_block = "\n".join(
            f"- {name}: {score:.2%}" for name, score in emotions.items()
        )

        prompt = (
            f"You are summarising what Reddit users in r/sydney say about "
            f"living in {suburb}. Based on the data below, write a concise "
            f"community narrative paragraph (3-5 sentences). Write as if "
            f"reporting on community sentiment — be specific, cite trends, "
            f"and mention both positives and negatives.\n\n"
            f"## Aspect Sentiment Scores\n{aspects_block}\n\n"
            f"## Emotion Profile\n{emotions_block}\n\n"
            f"## Sample Posts\n{texts_block}"
        )

        response = self._llm.invoke([HumanMessage(content=prompt)])
        return response.content


def get_synthesiser() -> Synthesiser:
    """Factory: return Claude synthesiser if enabled, otherwise mock."""
    if os.getenv("USE_CLAUDE_SYNTHESIS", "").lower() == "true":
        return ClaudeSynthesiser()
    return MockSynthesiser()
