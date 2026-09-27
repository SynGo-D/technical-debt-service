import json

from ..domain.finding import AnalysisFinding
from ..domain.agent_outputs import ClassificationOutput
from .llm_client import LLMClient


class ClassificationAgent:

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def classify(
        self,
        finding: AnalysisFinding
    ) -> ClassificationOutput:

        system_prompt = """
You are a software technical-debt classification agent.

Classify the supplied static-analysis finding.

Return ONLY valid JSON.

Required fields:

{
  "debt_type": "...",
  "impact": "...",
  "risk": "...",
  "complexity": "...",
  "confidence": 0.0,
  "reason": "..."
}

Allowed debt_type values:

SECURITY
BUG
MAINTAINABILITY
PERFORMANCE
RELIABILITY
DUPLICATION
TESTABILITY
ARCHITECTURE
DOCUMENTATION

Allowed impact values:

LOW
MEDIUM
HIGH
CRITICAL

Allowed risk values:

LOW
MEDIUM
HIGH
CRITICAL

Allowed complexity values:

LOW
MEDIUM
HIGH
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
Language: {finding.metadata.get("language")}
"""

        response = await self.llm.generate(
            system_prompt,
            user_prompt
        )

        data = json.loads(response)

        return ClassificationOutput(**data)