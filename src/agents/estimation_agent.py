from ..domain.finding import AnalysisFinding
from ..domain.agent_outputs import (
    DebtClassification,
    EffortEstimation,
)
from ..infrastructure.llm_client import LLMClient


class DebtEstimationAgent:

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def estimate(
        self,
        finding: AnalysisFinding,
        classification: DebtClassification,
    ) -> EffortEstimation:

        prompt = f"""
You are a software maintenance effort estimation specialist.

Estimate the effort required to fix the following issue.

Finding:
{finding.message}

Tool:
{finding.tool}

Rule:
{finding.rule_id}

File:
{finding.file_path}

Severity:
{finding.severity}

Category:
{finding.category}

Debt type:
{classification.debt_type}

Impact:
{classification.impact}

Risk:
{classification.risk}

Complexity:
{classification.complexity}

Estimate the remediation time in minutes.

Consider:

- scope of the issue
- likely code changes
- testing effort
- potential regression risk
- issue complexity

Return JSON only with:

estimated_minutes
confidence
recommendation
reasoning
"""

        return await self.llm.generate_structured(
            prompt,
            EffortEstimation,
        )

def validate_effort(
    minutes: int,
    finding
) -> int:

    if finding.category == "style":
        return min(minutes, 30)

    if finding.category == "unused_code":
        return min(minutes, 30)

    if finding.category == "vulnerability":
        return min(minutes, 480)

    return min(minutes, 240)