class HealthCalculator:

    def calculate(
        self,
        total_findings: int,
        critical: int,
        high: int,
        debt_hours: float,
        lines_changed: int
    ) -> int:

        score = 100

        score -= critical * 15
        score -= high * 8
        score -= total_findings * 2

        if lines_changed > 0:

            debt_ratio = (
                debt_hours * 60
            ) / lines_changed

            if debt_ratio > 0.50:
                score -= 10

            elif debt_ratio > 0.25:
                score -= 5

        return max(
            0,
            min(100, score)
        )
    
    def health_status(score: int) -> str:

        if score >= 90:
            return "HEALTHY"

        if score >= 70:
            return "GOOD"

        if score >= 50:
            return "NEEDS_ATTENTION"

        return "CRITICAL"