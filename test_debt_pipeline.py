import asyncio
import json
from uuid import uuid4

from src.agents.llm_client import LLMClient
from src.agents.classification_agent import ClassificationAgent
from src.agents.estimation_agent import EstimationAgent

from src.domain.finding import AnalysisFinding
from src.domain.debt import DebtCalculationRequest

from src.services.aggregator import DebtAggregator
from src.services.cost_calculator import CostCalculator
from src.services.health_calculator import HealthCalculator

from src.services.debt_service import DebtService

from src.config import settings


async def main():

    print("\n======================================")
    print("TECHNICAL DEBT PIPELINE TEST")
    print("======================================\n")

    # ------------------------------------------------
    # 1. Create test finding
    # ------------------------------------------------

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

        message="Use of eval detected. eval() can execute arbitrary code and create a security vulnerability.",

        tool="eslint",

        fingerprint="test-security-eval-001",

        metadata={
            "language": "javascript"
        }
    )

    # ------------------------------------------------
    # 2. Create request
    # ------------------------------------------------

    request = DebtCalculationRequest(

        repository="SynGo-D/test-repository",

        pull_request_number=42,

        commit_sha="abc123",

        lines_added=120,

        lines_removed=20,

        files_changed=5,

        findings=[finding]
    )

    print("STEP 1 — TEST FINDING")
    print("--------------------------------------")

    print(
        json.dumps(
            finding.model_dump(mode="json"),
            indent=2
        )
    )

    # ------------------------------------------------
    # 3. Create agents
    # ------------------------------------------------

    llm_client = LLMClient()

    classification_agent = ClassificationAgent(
        llm_client
    )

    estimation_agent = EstimationAgent(
        llm_client
    )

    # ------------------------------------------------
    # 4. Create calculation services
    # ------------------------------------------------

    aggregator = DebtAggregator()

    cost_calculator = CostCalculator(
        hourly_rate=settings.developer_hourly_rate
    )

    health_calculator = HealthCalculator()

    # ------------------------------------------------
    # 5. Create main debt service
    # ------------------------------------------------

    debt_service = DebtService(

        classification_agent=
            classification_agent,

        estimation_agent=
            estimation_agent,

        aggregator=
            aggregator,

        cost_calculator=
            cost_calculator,

        health_calculator=
            health_calculator
    )

    # ------------------------------------------------
    # 6. Run complete pipeline
    # ------------------------------------------------

    print("\nSTEP 2 — RUNNING AGENTS")
    print("--------------------------------------")

    result = await debt_service.calculate(
        request
    )

    # ------------------------------------------------
    # 7. Print result
    # ------------------------------------------------

    print("\nSTEP 3 — FINAL RESULT")
    print("--------------------------------------")

    print(
        json.dumps(
            result,
            indent=2,
            default=str
        )
    )

    # ------------------------------------------------
    # 8. Print dashboard summary
    # ------------------------------------------------

    print("\n======================================")
    print("DASHBOARD SUMMARY")
    print("======================================")

    summary = result["summary"]

    print(
        f"Total findings     : "
        f"{summary['total_findings']}"
    )

    print(
        f"Technical debt     : "
        f"{summary['total_debt_hours']} hours"
    )

    print(
        f"Estimated cost     : "
        f"${summary['estimated_cost']}"
    )

    print(
        f"Debt ratio         : "
        f"{summary['debt_ratio']}"
    )

    print(
        f"Health score       : "
        f"{summary['health_score']}/100"
    )

    print(
        f"Health status      : "
        f"{summary['health_status']}"
    )


if __name__ == "__main__":

    asyncio.run(main())