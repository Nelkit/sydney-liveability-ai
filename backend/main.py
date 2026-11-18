"""FastAPI entry point for Sydney Liveability Explorer backend."""

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.reddit_router import router as reddit_router
from api.router import router as system_router
from api.chat import router as chat_router
from api.civic import router as civic_router
from config import settings


_DESCRIPTION = """
## Sydney Liveability AI — REST API

Multi-agent backend that combines **civic GIS data**, **BOCSAR crime statistics**,
and **Reddit community sentiment** to answer natural-language questions about Sydney
suburbs.

### Architecture

```
User question
    │
    ▼
Router agent          — classifies intent (crime / sentiment / GIS / comparator / ranking)
    │
    ├─▶ Crime agent      — BOCSAR per-100k offence rates
    ├─▶ Sentiment agent  — Agentic RAG over Reddit chunks (ChromaDB + MiniLM)
    ├─▶ GIS agent        — ArcGIS facilities + OSM amenities + transport scores
    └─▶ Comparator agent — side-by-side suburb comparison
         │
         ▼
    Synthesiser         — merges specialist outputs into a single grounded answer
```

### Data sources

| Source | Coverage | Update cadence |
|--------|----------|---------------|
| ArcGIS / City of Sydney | Facilities, walkability | Annual |
| OpenStreetMap | Cafes, parks, hospitals, gyms | Monthly |
| BOCSAR | Crime offences per 100k | Quarterly |
| Reddit r/sydney + suburb subreddits | Community sentiment | Static snapshot |
| TfNSW GTFS | Bus / train / light-rail stop counts | Annual |

### Streaming

`POST /api/chat/stream` returns **Server-Sent Events** (SSE).
Each event has the form `event: <type>\\ndata: <json>\\n\\n`.
Event types: `step` (progress update) · `heartbeat` (keep-alive) · `done` (final payload) · `error`.
"""

logger = logging.getLogger("uvicorn.error")


def _warm_up() -> None:
    """Pay one-off loading costs at boot instead of on the first visitor's request.

    Each step is independent and best-effort: if one fails (e.g. the database
    is unreachable at boot) the server still starts and that resource loads
    lazily on first use, exactly as before.
    """
    from core.embeddings import get_embedder
    from core.scoring import _get_raw
    from db.chromadb import initialize_collection

    steps = (
        ("MiniLM embedder", get_embedder),
        ("ChromaDB collection", initialize_collection),
        # Fills core.scoring._RAW_CACHE so compute_liveability_scores() stops
        # querying the database (it runs twice per chat turn).
        ("liveability score components", lambda: _get_raw(None)),
    )
    for label, step in steps:
        started = time.perf_counter()
        try:
            step()
            logger.info("Warm-up: %s ready in %.1fs", label, time.perf_counter() - started)
        except Exception as exc:  # noqa: BLE001 - startup must never crash on warm-up
            logger.warning("Warm-up: %s failed (%s); it will load on first use.", label, exc)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _warm_up()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Sydney Liveability AI",
    description=_DESCRIPTION,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "chat",
            "description": (
                "Natural-language Q&A over Sydney suburbs. "
                "Use `/api/chat` for a single JSON response or `/api/chat/stream` "
                "for a live SSE stream with step-by-step progress."
            ),
        },
        {
            "name": "civic",
            "description": (
                "Structured suburb scores from PostgreSQL (ArcGIS + OSM + BOCSAR). "
                "Returns a GeoJSON FeatureCollection ranked by a user-supplied weight vector."
            ),
        },
        {
            "name": "reddit",
            "description": (
                "Pre-computed NLP analysis of Reddit posts per suburb: "
                "aspect sentiment (DeBERTa-v3), GoEmotions profile, and community narrative."
            ),
        },
        {
            "name": "system",
            "description": "Health check and service metadata.",
        },
    ],
    contact={
        "name": "AT2B Group — MDSI UNSW",
        "email": "nelkitisael792@gmail.com",
    },
    license_info={
        "name": "MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(civic_router)
app.include_router(system_router)
app.include_router(reddit_router)


@app.get("/", tags=["system"], summary="Service info", include_in_schema=False)
def project_info() -> dict[str, object]:
    """Return basic service metadata."""
    return {
        "project": "Sydney Liveability AI",
        "description": "Conversational and spatially-aware platform for Sydney suburbs.",
        "docs": "/docs",
    }


@app.get(
    "/health",
    tags=["system"],
    summary="Health check",
    response_description="Always `{status: ok}` when the service is up.",
)
def health() -> dict[str, str]:
    """Liveness probe used by Render and local Docker health checks."""
    return {"status": "ok"}
