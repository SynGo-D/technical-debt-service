from fastapi import APIRouter, HTTPException, Request

router = APIRouter(
    prefix="/api/repositories/{owner}/{repo}/debt-input",
    tags=["debt-input"],
)


@router.get("")
async def get_debt_input(
    owner: str,
    repo: str,
    pull_request_number: int,
    request: Request,
):
    repository = f"{owner}/{repo}"

    data = await request.app.state.analysis_result_repository.get_debt_input(
        repository,
        pull_request_number,
    )

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="No completed analysis found for this pull request.",
        )

    return data