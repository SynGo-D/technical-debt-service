import httpx

from ..config import settings


class LLMClient:

    def __init__(self):

        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:

        url = f"{self.base_url}/responses"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,

            "instructions": system_prompt,

            "input": user_prompt,

        }

        async with httpx.AsyncClient(
            timeout=120
        ) as client:

            response = await client.post(
                url,
                headers=headers,
                json=payload
            )

            if response.status_code != 200:

                print("\n========== LLM ERROR ==========")

                print(
                    "Status:",
                    response.status_code
                )

                print(
                    "Response:",
                    response.text
                )

                print(
                    "URL:",
                    url
                )

                print(
                    "Model:",
                    self.model
                )

                print("===============================\n")

            response.raise_for_status()

            data = response.json()

            # Responses API returns the generated
            # text in output items.

            for item in data.get("output", []):

                if item.get("type") == "message":

                    for content in item.get(
                        "content",
                        []
                    ):

                        if content.get(
                            "type"
                        ) == "output_text":

                            return content.get(
                                "text",
                                ""
                            )

            raise RuntimeError(
                "LLM returned no output text."
            )