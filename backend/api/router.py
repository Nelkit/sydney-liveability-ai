"""System endpoints — health check and service metadata."""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    summary="Health check",
    response_description="`{status: ok}` when the service is healthy.",
)
def health() -> dict:
    """Liveness probe for Render, Docker, and load-balancer health checks.

    Returns HTTP 200 with `{"status": "ok"}` whenever the process is running.
    Does **not** check database connectivity — use `/api/civic` for a
    deeper readiness check.
    """
    return {"status": "ok"}
