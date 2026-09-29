import asyncio

from src.agents.llm_client import LLMClient


async def main():

    print("Testing LLM connection...")

    client = LLMClient()

    response = await client.generate(

        system_prompt=(
            "You are a test assistant. "
            "Respond with only the word: SUCCESS"
        ),

        user_prompt=(
            "Test whether the API connection works."
        )
    )

    print("\nLLM RESPONSE:")
    print(response)


if __name__ == "__main__":

    asyncio.run(main())