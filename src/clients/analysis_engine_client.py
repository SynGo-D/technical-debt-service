import httpx

from ..config import settings


class AnalysisEngineClient:

    def __init__(self):

        self.base_url = settings.analysis_engine_url.rstrip("/")

    async def get_findings(
        self,
        repository: str,
        pull_request_number: int,
        commit_sha: str,
    ) -> dict:

        url = (
            f"{self.base_url}"
            "/api/analysis/findings"
        )

        params = {
            "repository": repository,
            "pull_request_number": pull_request_number,
            "commit_sha": commit_sha,
        }

        async with httpx.AsyncClient(
            timeout=120
        ) as client:

            response = await client.get(
                url,
                params=params
            )

            response.raise_for_status()

            return response.json()