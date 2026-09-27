class DebtAggregator:

    def aggregate(
        self,
        results: list[dict]
    ) -> dict:

        total_minutes = sum(
            item["estimated_minutes"]
            for item in results
        )

        critical = sum(
            1
            for item in results
            if item["risk"] == "CRITICAL"
        )

        high = sum(
            1
            for item in results
            if item["risk"] == "HIGH"
        )

        return {
            "total_findings": len(results),
            "total_debt_minutes": total_minutes,
            "total_debt_hours": round(
                total_minutes / 60,
                2
            ),
            "critical_issues": critical,
            "high_risk_issues": high
        }