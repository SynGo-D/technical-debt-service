import json

from ..domain.finding import AnalysisFinding
from ..domain.agent_outputs import (
    ClassificationOutput,
    EstimationOutput
)

from .llm_client import LLMClient


class EstimationAgent:

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def estimate(
        self,
        finding: AnalysisFinding,
        classification: ClassificationOutput
    ) -> EstimationOutput:

        system_prompt = """
You are a software remediation-effort estimation agent.

Estimate the developer effort required to fix the supplied issue.

Return ONLY valid JSON.

Required fields:

{
  "estimated_minutes": 0,
  "confidence": 0.0,
  "recommendation": "...",
  "reasoning": "..."
}

Use realistic development effort.

Do not estimate extremely large values for a single static-analysis issue
unless the finding clearly requires architectural changes.
"""

        user_prompt = f"""
Finding:

Tool: {finding.tool}
Rule: {finding.rule_id}
Severity: {finding.severity}
Category: {finding.category}
File: {finding.file_path}
Line: {finding.line}
Message: {finding.message}

Classification:

Debt type: {classification.debt_type}
Impact: {classification.impact}
Risk: {classification.risk}
Complexity: {classification.complexity}
"""

        response = await self.llm.generate(
            system_prompt,
            user_prompt
        )

        data = json.loads(response)

        return EstimationOutput(**data)