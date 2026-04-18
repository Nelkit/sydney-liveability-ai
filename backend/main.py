import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.reddit_router import router as reddit_router
from api.router import router as system_router


app = FastAPI(
    title="Sydney Liveability AI API",
    description=(
        "Backend API for Sydney Liveability AI. "
        "This service will expose civic and chat endpoints in later iterations."
    ),
    version="0.1.0",
)

# CORS for local dev + configured frontend URL.
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_frontend_url = os.getenv("FRONTEND_URL")
if _frontend_url:
    _default_origins.append(_frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(reddit_router)
