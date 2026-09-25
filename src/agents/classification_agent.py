from ..domain.finding import AnalysisFinding
from ..domain.agent_outputs import DebtClassification
from ..infrastructure.llm_client import LLMClient


class DebtClassificationAgent:

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def classify(
        self,
        finding: AnalysisFinding,
    ) -> DebtClassification:

        prompt = f"""
You are a software technical-debt classification specialist.

Analyze the following static-analysis finding.

Tool:
{finding.tool}

Rule:
{finding.rule_id}

File:
{finding.file_path}

Line:
{finding.line}

Severity:
{finding.severity}

Category:
{finding.category}

Message:
{finding.message}

Determine:

1. debt_type
2. business/technical impact
3. risk
4. implementation complexity
5. confidence
6. short explanation

Return JSON only.
"""

        return await self.llm.generate_structured(
            prompt,
            DebtClassification,
        )