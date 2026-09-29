import json

from ..domain.agent_outputs import ClassificationOutput
from ..domain.finding import AnalysisFinding
from .llm_client import LLMClient


class ClassificationAgent:

    def __init__(self, llm: LLMClient):

        self.llm = llm

    async def classify(
        self,
        finding: AnalysisFinding
    ) -> ClassificationOutput:

        system_prompt = """
You are a technical debt classification agent.

Analyze a static-analysis finding and classify its
technical debt characteristics.

Return ONLY valid JSON.

The JSON must contain:

{
  "debt_type": "...",
  "impact": "...",
  "risk": "...",
  "complexity": "...",
  "confidence": 0.0,
  "reason": "..."
}

Allowed debt types:

SECURITY
BUG
MAINTAINABILITY
PERFORMANCE
RELIABILITY
DUPLICATION
TESTABILITY
ARCHITECTURE
DOCUMENTATION

Allowed levels:

LOW
MEDIUM
HIGH
CRITICAL
"""

        user_prompt = f"""
Tool: {finding.tool}

Rule: {finding.rule_id}

Severity: {finding.severity}

Category: {finding.category}

File: {finding.file_path}

Line: {finding.line}

Message:
{finding.message}

Language:
{finding.metadata.get("language", "unknown")}
"""

        response = await self.llm.generate(
            system_prompt,
            user_prompt
        )

        data = json.loads(response)

        return ClassificationOutput(
            **data
        )