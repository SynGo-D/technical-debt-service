from ..domain.agent_outputs import (
    DebtClassification,
    EffortEstimation,
)
from ..domain.finding import AnalysisFinding


class DebtAggregator:

    def aggregate(
        self,
        findings,
        classifications,
        estimations,
    ):

        total_minutes = 0

        critical = 0
        high = 0
        medium = 0
        low = 0

        security = 0
        bugs = 0
        maintainability = 0

        issues = []

        for finding, classification, estimation in zip(
            findings,
            classifications,
            estimations,
        ):

            minutes = max(
                1,
                estimation.estimated_minutes,
            )

            total_minutes += minutes

            if classification.risk == "CRITICAL":
                critical += 1
            elif classification.risk == "HIGH":
                high += 1
            elif classification.risk == "MEDIUM":
                medium += 1
            else:
                low += 1

            if classification.debt_type == "SECURITY":
                security += 1

            if classification.debt_type == "BUG":
                bugs += 1

            if classification.debt_type == "MAINTAINABILITY":
                maintainability += 1

            issues.append({
                "finding_id": finding.finding_id,
                "minutes": minutes,
                "debt_type": classification.debt_type,
                "impact": classification.impact,
                "risk": classification.risk,
                "confidence": (
                    classification.confidence
                    * estimation.confidence
                ),
                "recommendation": (
                    estimation.recommendation
                ),
            })

        return {
            "total_debt_minutes": total_minutes,
            "critical_issues": critical,
            "high_risk_issues": high,
            "medium_risk_issues": medium,
            "low_risk_issues": low,
            "security_issues": security,
            "bugs": bugs,
            "maintainability_issues": maintainability,
            "issues": issues,
        }