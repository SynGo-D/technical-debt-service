class HealthCalculator:

    FINDING_WEIGHT = 1.5
    CRITICAL_WEIGHT = 8
    HIGH_WEIGHT = 4
    SECURITY_WEIGHT = 10
    DEBT_HOUR_WEIGHT = 2

    def calculate(
        self,
        total_findings: int,
        critical: int,
        high: int,
        security: int,
        debt_hours: float,
    ) -> int:

        penalty = (
            total_findings * self.FINDING_WEIGHT
            + critical * self.CRITICAL_WEIGHT
            + high * self.HIGH_WEIGHT
            + security * self.SECURITY_WEIGHT
            + debt_hours * self.DEBT_HOUR_WEIGHT
        )

        score = 100 - penalty

        return max(0, min(100, round(score)))


def health_status(score: int) -> str:

    if score >= 80:
        return "HEALTHY"
    elif score >= 60:
        return "NEEDS_ATTENTION"
    elif score >= 40:
        return "AT_RISK"
    else:
        return "CRITICAL"