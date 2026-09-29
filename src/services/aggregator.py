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
            item["risk"] == "CRITICAL"
            for item in results
        )

        high = sum(
            item["risk"] == "HIGH"
            for item in results
        )

        medium = sum(
            item["risk"] == "MEDIUM"
            for item in results
        )

        low = sum(
            item["risk"] == "LOW"
            for item in results
        )

        security = sum(
            item["debt_type"] == "SECURITY"
            for item in results
        )

        bugs = sum(
            item["debt_type"] == "BUG"
            for item in results
        )

        maintainability = sum(
            item["debt_type"] == "MAINTAINABILITY"
            for item in results
        )

        return {

            "total_findings":
                len(results),

            "total_debt_minutes":
                total_minutes,

            "total_debt_hours":
                round(
                    total_minutes / 60,
                    2
                ),

            "critical_issues":
                critical,

            "high_risk_issues":
                high,

            "medium_risk_issues":
                medium,

            "low_risk_issues":
                low,

            "security_issues":
                security,

            "bugs":
                bugs,

            "maintainability_issues":
                maintainability
        }