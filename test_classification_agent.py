import asyncio
from uuid import uuid4

from src.agents.llm_client import LLMClient
from src.agents.classification_agent import ClassificationAgent
from src.domain.finding import AnalysisFinding


async def main():

    finding = AnalysisFinding(

        finding_id=uuid4(),

        repository="SynGo-D/test-repository",

        pull_request_number=42,

        commit_sha="abc123",

        file_path="src/auth.js",

        line=25,

        column=10,

        severity="HIGH",

        category="SECURITY",

        rule_id="security/eval",

        message=(
            "Use of eval detected. "
            "eval() can execute arbitrary code."
        ),

        tool="eslint",

        fingerprint="test-security-eval-001",

        metadata={
            "language": "javascript"
        }
    )

    llm = LLMClient()

    agent = ClassificationAgent(llm)

    result = await agent.classify(finding)

    print("\nCLASSIFICATION RESULT")
    print("=====================")

    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":

    asyncio.run(main())