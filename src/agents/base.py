import json
import logging
import re

from .llm_client import LLMClient, LLMError

logger = logging.getLogger(__name__)


class AgentError(RuntimeError):
    pass


def parse_json_object(text: str) -> dict:
    """Models sometimes wrap JSON in ```json fences or add a sentence around it."""

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise AgentError(f"No JSON object in model reply: {text[:200]!r}")
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            raise AgentError(f"Invalid JSON in model reply: {e}") from e

    if not isinstance(data, dict):
        raise AgentError("Model reply is not a JSON object")

    return data


class BaseAgent:
    """Shared plumbing: call the LLM, parse JSON, retry once."""

    attempts = 2

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def ask_json(self, system_prompt: str, user_prompt: str) -> dict:

        last: Exception | None = None

        for attempt in range(1, self.attempts + 1):
            try:
                return parse_json_object(
                    await self.llm.generate(system_prompt, user_prompt)
                )
            except (AgentError, LLMError) as e:
                last = e
                logger.warning(
                    "%s attempt %d/%d failed: %s",
                    type(self).__name__, attempt, self.attempts, e,
                )
                # A missing key will not fix itself on retry.
                if isinstance(e, LLMError) and "not set" in str(e):
                    break

        raise AgentError(str(last))
