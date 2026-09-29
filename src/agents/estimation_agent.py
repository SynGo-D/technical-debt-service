import logging

from ..domain.agent_outputs import (
    MAX_MINUTES,
    MIN_MINUTES,
    ClassificationOutput,
    EstimationOutput,
)
from ..domain.finding import AnalysisFinding
from .base import AgentError, BaseAgent

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are a software remediation effort estimation agent.

Estimate the amount of developer time required to fix
the supplied technical debt issue.

Return ONLY valid JSON.

Format:

{
  "estimated_minutes": 0,
  "confidence": 0.0,
  "recommendation": "...",
  "reasoning": "..."
}

Use realistic estimates.

Do not use extremely large estimates for simple
static-analysis issues.
"""

_DEFAULT_MINUTES = {"LOW": 15, "MEDIUM": 30, "HIGH": 60, "CRITICAL": 120}


def _clamp_minutes(minutes: int) -> int:
    return min(MAX_MINUTES, max(MIN_MINUTES, minutes))


class EstimationAgent(BaseAgent):
    """Agent 2: how long will it take to fix, and how?"""

    async def estimate(
        self,
        finding: AnalysisFinding,
        classification: ClassificationOutput
    ) -> EstimationOutput:

        user_prompt = f"""
Finding:

Tool: {finding.tool}

Rule: {finding.rule_id}

Severity: {finding.severity}

Category: {finding.category}

File:
{finding.file_path}

Line:
{finding.line}

Message:
{finding.message}


Classification:

Debt type:
{classification.debt_type}

Impact:
{classification.impact}

Risk:
{classification.risk}

Complexity:
{classification.complexity}
"""

        try:
            data = await self.ask_json(SYSTEM_PROMPT, user_prompt)
            minutes = round(float(data["estimated_minutes"]))
            confidence = min(1.0, max(0.0, float(data.get("confidence", 0.5))))
        except (AgentError, KeyError, TypeError, ValueError) as e:
            logger.warning(
                "estimation fell back for %s: %s", finding.finding_id, e
            )
            return self._fallback(finding, classification)

        return EstimationOutput(
            estimated_minutes=_clamp_minutes(minutes),
            confidence=confidence,
            recommendation=str(data.get("recommendation") or ""),
            reasoning=str(data.get("reasoning") or ""),
        )

    @staticmethod
    def _fallback(
        finding: AnalysisFinding,
        classification: ClassificationOutput
    ) -> EstimationOutput:

        # analysis-engine's own SQALE-style figure beats a generic default.
        minutes = finding.remediation_minutes or _DEFAULT_MINUTES.get(
            classification.risk, 30
        )

        return EstimationOutput(
            estimated_minutes=_clamp_minutes(minutes),
            confidence=0.3,
            recommendation=f"Fix the {finding.rule_id} violation in {finding.file_path}.",
            reasoning="Derived from analysis-engine remediation_minutes/risk (LLM unavailable).",
        )
