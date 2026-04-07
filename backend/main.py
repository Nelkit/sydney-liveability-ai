from fastapi import FastAPI

from api.router import router as system_router
from core.osm_data import load_osm_scores, load_suburbs_geojson


app = FastAPI(
    title="Sydney Liveability AI API",
    description=(
        "Backend API for Sydney Liveability AI. "
        "This service will expose civic and chat endpoints in later iterations."
    ),
    version="0.1.0",
)


@app.on_event("startup")
def load_precomputed_data() -> None:
    app.state.osm_scores = load_osm_scores()
    app.state.suburbs_geojson = load_suburbs_geojson()

app.include_router(system_router)
