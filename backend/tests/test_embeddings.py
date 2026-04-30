"""Unit tests for backend/core/embeddings.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("sentence_transformers")

from core.embeddings import get_embedder  # noqa: E402


def test_get_embedder_is_singleton() -> None:
    """Two calls return the same model object so coverage and ChromaDB share one load."""
    first = get_embedder()
    second = get_embedder()
    assert first is second
