"""Per-dimension coverage detection via sentence-transformer similarity."""

from __future__ import annotations

from typing import Literal

CoverageTier = Literal["none", "weak", "strong"]

# Hand-written prototype sentence per liveability dimension. Kept in this
# module (not aspects.py) because coverage answers a different question
# (whether the topic is talked about) than aspect classification (how the
# topic is talked about). Order mirrors ASPECT_TAXONOMY.
DIMENSION_PROTOTYPES: dict[str, str] = {
    "safety": "safety, crime, feeling safe walking around the area at night",
    "food_and_cafe": "cafes, restaurants, brunch spots, eating out in the area",
    "nightlife": "nightlife, bars, pubs, going out, live music in the area",
    "affordability": "rent prices, housing affordability, cost of living in the area",
    "transport": "public transport, trains, buses, and commuting around the area",
    "community": "community, neighbours, local people, neighbourhood vibe",
    "noise": "noise levels, how loud or quiet the area is at night",
    "green_space": "parks, trees, green space, nature and outdoor walks",
}

# Tier thresholds tuned against a 30-suburb hand-labelled sample; see
# openspec/changes/deepen-reddit-transformer-pipeline/design.md §1 for the
# methodology and the report for the experiment write-up.
WEAK_SIMILARITY_THRESHOLD = 0.25
STRONG_SIMILARITY_THRESHOLD = 0.4

# Top-k similarity scores averaged into the per-dimension signal. Matches
# the "10 mentions = full confidence" idiom used elsewhere in the pipeline.
TOP_K = 10

_prototype_embeddings: dict[str, "list[float]"] | None = None


def _get_encoder():
    # Shared singleton with backend/db/chromadb.py so the model loads once
    # per process. See backend/core/embeddings.py for the rationale.
    from core.embeddings import get_embedder

    return get_embedder()


def _get_prototype_embeddings():
    global _prototype_embeddings
    if _prototype_embeddings is None:
        encoder = _get_encoder()
        names = list(DIMENSION_PROTOTYPES.keys())
        sentences = [DIMENSION_PROTOTYPES[n] for n in names]
        embeddings = encoder.encode(
            sentences, normalize_embeddings=True, convert_to_numpy=True
        )
        _prototype_embeddings = dict(zip(names, embeddings))
    return _prototype_embeddings


def _tier_for(similarity: float) -> CoverageTier:
    if similarity >= STRONG_SIMILARITY_THRESHOLD:
        return "strong"
    if similarity >= WEAK_SIMILARITY_THRESHOLD:
        return "weak"
    return "none"


def compute_coverage(texts: list[str]) -> dict[str, dict]:
    """Return per-dimension coverage given a corpus of suburb posts.

    Each entry is `{tier, mention_count, prototype_similarity}` where
    `mention_count` is the number of posts whose cosine similarity to the
    dimension prototype exceeds WEAK_SIMILARITY_THRESHOLD.
    """
    result: dict[str, dict] = {}
    if not texts:
        for name in DIMENSION_PROTOTYPES:
            result[name] = {
                "tier": "none",
                "mention_count": 0,
                "prototype_similarity": 0.0,
            }
        return result

    import numpy as np

    encoder = _get_encoder()
    prototypes = _get_prototype_embeddings()

    post_embeddings = encoder.encode(
        texts, normalize_embeddings=True, convert_to_numpy=True
    )

    for name, proto in prototypes.items():
        sims = post_embeddings @ np.asarray(proto)
        # mean of top-K (or all if fewer than K posts), as the dimension
        # similarity signal — robust to a long tail of unrelated posts.
        k = min(TOP_K, len(sims))
        top_k = np.partition(sims, -k)[-k:] if k > 0 else sims
        mean_top_k = float(np.mean(top_k)) if k > 0 else 0.0

        mention_count = int(np.sum(sims >= WEAK_SIMILARITY_THRESHOLD))

        result[name] = {
            "tier": _tier_for(mean_top_k),
            "mention_count": mention_count,
            "prototype_similarity": round(mean_top_k, 4),
        }

    return result
