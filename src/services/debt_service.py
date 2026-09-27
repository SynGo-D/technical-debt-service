class DebtService:

    def __init__(
        self,
        classification_agent,
        estimation_agent,
        aggregator,
        cost_calculator,
        health_calculator
    ):
        self.classification_agent = classification_agent
        self.estimation_agent = estimation_agent
        self.aggregator = aggregator
        self.cost_calculator = cost_calculator
        self.health_calculator = health_calculator

    async def calculate(self, request):

        results = []

        for finding in request.findings:

            classification = (
                await self.classification_agent.classify(
                    finding
                )
            )

            estimation = (
                await self.estimation_agent.estimate(
                    finding,
                    classification
                )
            )

            results.append({
                "finding_id": finding.finding_id,

                "file_path": finding.file_path,

                "line": finding.line,

                "tool": finding.tool,

                "rule_id": finding.rule_id,

                "debt_type":
                    classification.debt_type,

                "impact":
                    classification.impact,

                "risk":
                    classification.risk,

                "complexity":
                    classification.complexity,

                "estimated_minutes":
                    estimation.estimated_minutes,

                "confidence":
                    estimation.confidence,

                "recommendation":
                    estimation.recommendation
            })

        summary = self.aggregator.aggregate(
            results
        )

        cost = self.cost_calculator.calculate(
            summary["total_debt_minutes"]
        )

        lines_changed = (
            request.lines_added +
            request.lines_removed
        )

        health = self.health_calculator.calculate(
            summary["total_findings"],
            summary["critical_issues"],
            summary["high_risk_issues"],
            summary["total_debt_hours"],
            lines_changed
        )

        return {
            "repository":
                request.repository,

            "pull_request_number":
                request.pull_request_number,

            "commit_sha":
                request.commit_sha,

            "summary": {
                **summary,

                "estimated_cost":
                    cost,

                "health_score":
                    health
            },

            "issues":
                results
        }