"""FastAPI entry point for Sydney Liveability Explorer backend."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.reddit_router import router as reddit_router
from api.router import router as system_router
from api.chat import router as chat_router
from api.civic import router as civic_router
from config import settings


app = FastAPI(
    title="Sydney Liveability AI API",
    description="Backend API for CrewAI-powered suburb analysis.",
    version="0.2.0",
)


@app.get("/")
def project_info() -> dict[str, object]:
    """Return basic service metadata while feature APIs are implemented."""
    return {
        "project": "Sydney Liveability AI",
        "description": "Conversational and spatially-aware platform for Sydney suburbs.",
        "upcoming_endpoints": ["/api/civic", "/api/chat"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Return backend health for local checks and deployment probes."""
    return {"status": "ok"}


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
