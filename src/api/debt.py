import logging

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from ..domain.debt import DebtCalculationRequest
from ..infrastructure.analysis_repository import AnalysisNotFound

logger = logging.getLogger(__name__)


# Same route shape as analysis-engine (/api/repositories/{owner}/{repo}/...)
# so a gateway can proxy both services the same way.
router = APIRouter(
    tags=["Technical Debt"]
)


async def _calculate_and_store(
    request: Request,
    payload: DebtCalculationRequest
) -> dict:

    state = request.app.state

    result = await state.debt_service.calculate(payload)

    saved = await state.debt_repository.save(result)

    return {
        "review": saved,
        "scope": result["scope"],
        "pre_existing_excluded": result["pre_existing_excluded"],
        "findings_received": result["findings_received"],
        "findings_skipped": result["findings_skipped"],
    }


@router.post("/api/debt/calculate")
async def calculate_from_findings(
    payload: DebtCalculationRequest,
    request: Request
):
    """Calculate + store debt for findings supplied in the body."""

    return await _calculate_and_store(request, payload)


@router.post(
    "/api/repositories/{owner}/{repo}/debt/pull-requests/{pull_request_number}/calculate"
)
async def calculate_for_pull_request(
    owner: str,
    repo: str,
    pull_request_number: int,
    request: Request
):
    """Read the PR's latest completed analysis from the analysis-engine
    database, run both agents, store and return the result. Slow (LLM calls)."""

    repository = f"{owner}/{repo}"

    try:
        payload = await request.app.state.analysis_repository.get_calculation_request(
            repository,
            pull_request_number,
        )

    except AnalysisNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    except (SQLAlchemyError, OSError) as e:
        logger.exception("analysis-engine database unreachable")
        raise HTTPException(
            status_code=502,
            detail=f"analysis-engine database unavailable: {type(e).__name__}",
        ) from None

    return await _calculate_and_store(request, payload)


@router.get("/api/debt/repositories")
async def list_repositories(request: Request):

    return {
        "repositories": await request.app.state.debt_repository.list_repositories()
    }


@router.get("/api/repositories/{owner}/{repo}/debt")
async def list_reviews(
    owner: str,
    repo: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
):

    repository = f"{owner}/{repo}"

    reviews = await request.app.state.debt_repository.list_reviews(repository, limit)

    return {"repository": repository, "reviews": reviews}


@router.get("/api/repositories/{owner}/{repo}/debt/summary")
async def repository_summary(owner: str, repo: str, request: Request):

    summary = await request.app.state.debt_repository.repository_summary(
        f"{owner}/{repo}"
    )

    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="No technical-debt reviews for this repository yet.",
        )

    return summary


@router.get(
    "/api/repositories/{owner}/{repo}/debt/pull-requests/{pull_request_number}"
)
async def get_pull_request_debt(
    owner: str,
    repo: str,
    pull_request_number: int,
    request: Request
):

    review = await request.app.state.debt_repository.get_latest_for_pull_request(
        f"{owner}/{repo}",
        pull_request_number,
    )

    if review is None:
        raise HTTPException(
            status_code=404,
            detail="No technical-debt review for this pull request yet.",
        )

    return review
