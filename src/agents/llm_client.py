import httpx

from ..config import settings


class LLMError(RuntimeError):
    pass


class LLMClient:
    """OpenAI Responses API client. Defaults come from settings, so
    `LLMClient()` works as before; one HTTP connection pool is reused."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):

        self.api_key = settings.llm_api_key if api_key is None else api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model

        self._http = httpx.AsyncClient(
            timeout=timeout or settings.llm_timeout_seconds,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:

        if not self.api_key:
            raise LLMError("LLM_API_KEY is not set")

        try:
            response = await self._http.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": system_prompt,
                    "input": user_prompt,
                },
            )
            response.raise_for_status()
            data = response.json()

        except httpx.HTTPStatusError as e:
            raise LLMError(
                f"LLM returned HTTP {e.response.status_code}: "
                f"{e.response.text[:300]}"
            ) from e

        except (httpx.HTTPError, ValueError) as e:
            raise LLMError(f"LLM call failed: {e!r}") from e

        # Responses API returns the generated text in output items.
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content.get("text", "")

        raise LLMError("LLM returned no output text.")

    async def aclose(self) -> None:
        await self._http.aclose()
