from fastapi import FastAPI

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

app.include_router(system_router)
app.include_router(reddit_router)
