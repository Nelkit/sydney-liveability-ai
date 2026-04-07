from fastapi import APIRouter

from api.civic import router as civic_router


router = APIRouter(tags=["system"])
router.include_router(civic_router)


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
