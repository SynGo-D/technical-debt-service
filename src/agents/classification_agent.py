import logging

from ..domain.agent_outputs import (
    COMPLEXITIES,
    DEBT_TYPES,
    LEVELS,
    ClassificationOutput,
)
from ..domain.finding import AnalysisFinding
from .base import AgentError, BaseAgent

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
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

Allowed levels (impact and risk):

LOW
MEDIUM
HIGH
CRITICAL

Allowed complexity values:

LOW
MEDIUM
HIGH
"""

# analysis-engine's category / severity vocabulary -> ours, for the fallback.
_CATEGORY_TO_TYPE = {
    "vulnerability": "SECURITY",
    "bug": "BUG",
    "code_smell": "MAINTAINABILITY",
    "style": "MAINTAINABILITY",
    "complexity": "MAINTAINABILITY",
    "cognitive_complexity": "MAINTAINABILITY",
    "maintainability": "MAINTAINABILITY",
    "unused_code": "MAINTAINABILITY",
}

_SEVERITY_TO_LEVEL = {"error": "HIGH", "warning": "MEDIUM", "info": "LOW"}


def _pick(value, allowed: tuple[str, ...], default: str) -> str:
    v = str(value or "").strip().upper()
    return v if v in allowed else default


class ClassificationAgent(BaseAgent):
    """Agent 1: what kind of debt is this, and how risky?"""

    async def classify(
        self,
        finding: AnalysisFinding
    ) -> ClassificationOutput:

        fallback = self._fallback(finding)

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

        try:
            data = await self.ask_json(SYSTEM_PROMPT, user_prompt)
        except AgentError as e:
            logger.warning(
                "classification fell back for %s: %s", finding.finding_id, e
            )
            return fallback

        try:
            confidence = min(1.0, max(0.0, float(data.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5

        # An out-of-vocabulary value from the model becomes the deterministic
        # default for just that field, not a failed review.
        return ClassificationOutput(
            debt_type=_pick(data.get("debt_type"), DEBT_TYPES, fallback.debt_type),
            impact=_pick(data.get("impact"), LEVELS, fallback.impact),
            risk=_pick(data.get("risk"), LEVELS, fallback.risk),
            complexity=_pick(data.get("complexity"), COMPLEXITIES, fallback.complexity),
            confidence=confidence,
            reason=str(data.get("reason") or ""),
        )

    @staticmethod
    def _fallback(finding: AnalysisFinding) -> ClassificationOutput:

        level = _SEVERITY_TO_LEVEL.get(finding.severity, "MEDIUM")

        return ClassificationOutput(
            debt_type=_CATEGORY_TO_TYPE.get(finding.category, "MAINTAINABILITY"),
            impact=level,
            risk=level,
            complexity="MEDIUM",
            confidence=0.3,
            reason="Derived from linter severity/category (LLM unavailable).",
        )
