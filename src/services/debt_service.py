import asyncio
import logging

from ..domain.debt import DebtCalculationRequest
from ..domain.finding import AnalysisFinding

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

_MAX_RATIO = 9999.9999  # debt_reviews.debt_ratio is NUMERIC(8,4)


class DebtService:
    """Runs both agents over a PR's findings and computes the summary.
    Pure calculation - persisting is DebtRepository's job."""

    def __init__(
        self,
        classification_agent,
        estimation_agent,
        aggregator,
        cost_calculator,
        health_calculator,
        concurrency: int = 5,
        max_findings: int = 200,
    ):

        self.classification_agent = classification_agent
        self.estimation_agent = estimation_agent
        self.aggregator = aggregator
        self.cost_calculator = cost_calculator
        self.health_calculator = health_calculator
        self.concurrency = concurrency
        self.max_findings = max_findings

    async def _assess(
        self,
        finding: AnalysisFinding,
        gate: asyncio.Semaphore
    ) -> dict:

        # Agent 1 then Agent 2 (which needs Agent 1's output) per finding;
        # different findings run concurrently, bounded by `gate`.
        async with gate:
            classification = await self.classification_agent.classify(finding)
            estimation = await self.estimation_agent.estimate(finding, classification)

        return {
            "finding_id": finding.finding_id,
            "file_path": finding.file_path,
            "line": finding.line,
            "tool": finding.tool,
            "rule_id": finding.rule_id,
            "debt_type": classification.debt_type,
            "impact": classification.impact,
            "risk": classification.risk,
            "complexity": classification.complexity,
            "estimated_minutes": estimation.estimated_minutes,
            "confidence": estimation.confidence,
            "recommendation": estimation.recommendation,
        }

    async def calculate(self, request: DebtCalculationRequest) -> dict:

        received = len(request.findings)

        findings = sorted(
            request.findings,
            key=lambda f: _SEVERITY_ORDER.get(f.severity, 3),
        )[: self.max_findings]

        gate = asyncio.Semaphore(self.concurrency)

        results = list(
            await asyncio.gather(*(self._assess(f, gate) for f in findings))
        )

        results.sort(
            key=lambda r: (_RISK_ORDER.get(r["risk"], 4), -r["estimated_minutes"])
        )

        summary = self.aggregator.aggregate(results)

        cost = self.cost_calculator.calculate(summary["total_debt_minutes"])

        lines_changed = request.lines_added + request.lines_removed

        health_score = self.health_calculator.calculate(
            total_findings=summary["total_findings"],
            critical=summary["critical_issues"],
            high=summary["high_risk_issues"],
            debt_hours=summary["total_debt_hours"],
            lines_changed=lines_changed,
        )

        # Debt minutes per changed line; unknown (None) when the PR diff
        # was unavailable rather than a misleading 0.
        debt_ratio = (
            round(min(summary["total_debt_minutes"] / lines_changed, _MAX_RATIO), 4)
            if lines_changed > 0
            else None
        )

        return {
            "repository": request.repository,
            "pull_request_number": request.pull_request_number,
            "commit_sha": request.commit_sha,
            "summary": {
                **summary,
                "estimated_cost": cost,
                "debt_ratio": debt_ratio,
                "health_score": health_score,
                "health_status": self.health_calculator.status(health_score),
            },
            "scope": request.scope,
            "pre_existing_excluded": request.pre_existing_excluded,
            "findings_received": received,
            "findings_skipped": received - len(findings),
            "issues": results,
        }
