from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter(
    tags=["Health"]
)


@router.get("/health")
async def health():
    """Liveness only."""

    return {
        "status": "ok",
        "service": "technical-debt-service"
    }


@router.get("/ready")
async def ready(request: Request):
    """Readiness: both databases reachable."""

    checks = {}

    for name, repo in (
        ("database", request.app.state.debt_repository),
        ("analysis_database", request.app.state.analysis_repository),
    ):
        try:
            await repo.ping()
            checks[name] = True
        except Exception:
            checks[name] = False

    ok = all(checks.values())

    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "service": "technical-debt-service",
            "ready": ok,
            "checks": checks,
        },
    )
