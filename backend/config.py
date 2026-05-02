"""Central configuration and LLM factory for CrewAI agents.

LLM configuration:
- LLM_MODEL sets the shared default model for every agent.
- LLM_AGENT_MODELS_JSON can override the model per agent without changing code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from crewai import LLM
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    _BASE_DIR = Path(__file__).resolve().parent
    model_config = SettingsConfigDict(
        env_file=(_BASE_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
    )

    llm_provider: str = "openrouter"
    llm_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    llm_agent_models_json: str = ""
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    walkscore_api_key: str = ""
    database_url: str = ""
    chromadb_path: str = "./data/chromadb"
    frontend_url: str = "http://localhost:3000"
    synthesis_debug_mode: str = "off"


settings = Settings()


def _normalise_provider(provider: Optional[str]) -> str:
    """Normalise provider names so callers can pass mixed-case values."""
    return (provider or settings.llm_provider).strip().lower()


def _require_api_key(api_key: str, provider: str) -> str:
    """Fail fast when a selected LLM provider has no API key configured."""
    if api_key.strip():
        return api_key
    msg = f"Missing API key for provider '{provider}'. Configure it in backend/.env."
    raise ValueError(msg)


@lru_cache(maxsize=1)
def _get_agent_model_overrides() -> dict[str, str]:
    """Return optional per-agent model overrides from env configuration."""
    raw_value = settings.llm_agent_models_json.strip()
    if not raw_value:
        return {}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        msg = "LLM_AGENT_MODELS_JSON must contain valid JSON."
        raise ValueError(msg) from exc

    if not isinstance(parsed, dict):
        msg = "LLM_AGENT_MODELS_JSON must be a JSON object mapping agent names to models."
        raise ValueError(msg)

    overrides: dict[str, str] = {}
    for agent_name, model_name in parsed.items():
        if isinstance(agent_name, str) and isinstance(model_name, str) and model_name.strip():
            overrides[agent_name.strip().lower()] = model_name.strip()

    return overrides


@lru_cache(maxsize=16)
def get_llm(provider: str | None = None, model: str | None = None) -> LLM:
    """Return a CrewAI LLM using env defaults, with optional per-agent override."""
    chosen_provider = _normalise_provider(provider)
    chosen_model = model or settings.llm_model

    if chosen_provider == "openrouter":
        return LLM(
            model=f"openrouter/{chosen_model}",
            base_url="https://openrouter.ai/api/v1",
            api_key=_require_api_key(settings.openrouter_api_key, "openrouter"),
        )
    if chosen_provider == "anthropic":
        return LLM(
            model=f"anthropic/{chosen_model}",
            api_key=_require_api_key(settings.anthropic_api_key, "anthropic"),
        )
    if chosen_provider == "openai":
        return LLM(
            model=f"openai/{chosen_model}",
            api_key=_require_api_key(settings.openai_api_key, "openai"),
        )

    msg = "Unsupported LLM provider. Use openrouter, anthropic, or openai."
    raise ValueError(msg)


def get_agent_llm(agent_name: str, provider: str | None = None, model: str | None = None) -> LLM:
    """Return the LLM for a specific agent, falling back to the shared default."""
    agent_key = agent_name.strip().lower()
    resolved_model = model or _get_agent_model_overrides().get(agent_key) or settings.llm_model
    return get_llm(provider=provider, model=resolved_model)
