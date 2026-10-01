import asyncio
import logging

from ..agents.base import AgentError
from ..agents.rule_matching_agent import languages_for, shortlist
from ..domain.agent_outputs import MAX_MINUTES, MIN_MINUTES
from ..domain.finding import AnalysisFinding

logger = logging.getLogger(__name__)

# SonarQube rule type -> debt type
_TYPE = {
    "BUG": "BUG",
    "VULNERABILITY": "SECURITY",
    "SECURITY_HOTSPOT": "SECURITY",
    "CODE_SMELL": "MAINTAINABILITY",
}

# SonarQube severity -> risk level
_RISK = {
    "BLOCKER": "CRITICAL",
    "CRITICAL": "HIGH",
    "MAJOR": "MEDIUM",
    "MINOR": "LOW",
    "INFO": "LOW",
}

# For rules SonarQube gives no remediation effort (security hotspots).
_DEFAULT_MINUTES = {"LOW": 15, "MEDIUM": 30, "HIGH": 60, "CRITICAL": 120}


def assessment_from_rule(rule) -> dict:
    """Debt values for one issue, read from its SonarQube rule. No model
    output is involved here."""
    risk = _RISK.get(rule.severity, "MEDIUM")

    minutes = rule.remediation_minutes or _DEFAULT_MINUTES[risk]

    return {
        "debt_type": _TYPE.get(rule.rule_type, "MAINTAINABILITY"),
        "impact": risk,
        "risk": risk,
        "complexity": "MEDIUM",
        "estimated_minutes": min(MAX_MINUTES, max(MIN_MINUTES, minutes)),
        "confidence": 1.0,
        "recommendation": f"SonarQube rule {rule.key}: {rule.name}.",
    }


class SonarDebtAssessor:
    """Finds the SonarQube rule for a finding and reads its debt values from
    the local catalog. The matching agent is asked once per linter rule; the
    answer is stored, so later runs need no LLM call for that rule."""

    def __init__(self, catalog, matching_agent):
        self.catalog = catalog
        self.matching_agent = matching_agent
        self._rules: dict[tuple[str, ...], list] = {}
        self._resolving: dict[tuple[str, str], asyncio.Task] = {}

    async def prepare(self) -> bool:
        """Call at the start of a run. False when the catalog has never been
        synced, so there is nothing to look values up in."""
        self._rules.clear()
        self._resolving.clear()
        return (await self.catalog.status())["rules"] > 0

    async def assess(self, finding: AnalysisFinding) -> dict | None:
        """Debt values from the finding's SonarQube rule; None when no
        equivalent rule exists."""
        key = (finding.tool, finding.rule_id)

        # Findings of the same linter rule share one resolution.
        task = self._resolving.get(key)

        if task is None:
            task = asyncio.ensure_future(self._resolve(finding))
            self._resolving[key] = task

        rule = await task

        return assessment_from_rule(rule) if rule else None

    async def _resolve(self, finding: AnalysisFinding):
        mapping = await self.catalog.get_mapping(finding.tool, finding.rule_id)

        if mapping is not None:
            if mapping.sonar_rule_key is None:
                return None
            return await self.catalog.get_rule(mapping.sonar_rule_key)

        candidates = shortlist(finding, await self._rules_for(finding))

        if not candidates:
            await self.catalog.save_mapping(finding.tool, finding.rule_id, None)
            return None

        try:
            chosen = await self.matching_agent.match(finding, candidates)
        except AgentError as e:
            # Not stored: the next run asks again once the LLM is back.
            logger.warning("rule matching unavailable for %s/%s: %s", *finding_key(finding), e)
            return None

        await self.catalog.save_mapping(finding.tool, finding.rule_id, chosen)

        return next((r for r in candidates if r.key == chosen), None)

    async def _rules_for(self, finding: AnalysisFinding) -> list:
        languages = tuple(languages_for(finding))

        if languages not in self._rules:
            self._rules[languages] = await self.catalog.rules_for_languages(list(languages))

        return self._rules[languages]


def finding_key(finding: AnalysisFinding) -> tuple[str, str]:
    return finding.tool, finding.rule_id
