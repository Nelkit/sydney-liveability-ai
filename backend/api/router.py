from fastapi import APIRouter


router = APIRouter(tags=["system"])


@router.get("/")
def project_info() -> dict:
    return {
        "project": "Sydney Liveability AI",
        "description": (
            "Conversational and spatially-aware platform to help users compare "
            "Sydney suburbs using civic data, crime statistics, and resident discourse."
        ),
        "upcoming_endpoints": ["/api/civic", "/api/chat"],
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}