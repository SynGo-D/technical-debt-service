from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.classification_agent import ClassificationAgent
from ..agents.estimation_agent import EstimationAgent
from ..agents.llm_client import LLMClient
from ..domain.finding import AnalysisFinding

from .aggregator import DebtAggregator
from .cost_calculator import CostCalculator
from .health_calculator import HealthCalculator
from .debt_repository import DebtRepository


class DebtService:

    def __init__(
        self,
        session: AsyncSession,
    ):

        self.session = session

        self.repository = DebtRepository(session)

        self.llm = LLMClient()

        self.classification_agent = ClassificationAgent(
            self.llm
        )

        self.estimation_agent = EstimationAgent(
            self.llm
        )

        self.aggregator = DebtAggregator()

        self.cost_calculator = CostCalculator(
            hourly_rate=25.0
        )

        self.health_calculator = HealthCalculator()

    async def calculate_debt(
        self,
        request,
    ):

        issues = []

        # ====================================================
        # PROCESS EVERY FINDING
        # ====================================================

        for finding in request.findings:

            # ----------------------------------------------
            # Convert request finding -> domain finding
            # ----------------------------------------------

            analysis_finding = AnalysisFinding(
                finding_id=UUID(
                    str(finding.finding_id)
                ),

                repository=request.repository,

                pull_request_number=
                    request.pull_request_number,

                commit_sha=request.commit_sha,

                file_path=finding.file_path,

                line=finding.line,

                column=finding.column,

                severity=finding.severity,

                category=finding.category,

                rule_id=finding.rule_id,

                message=finding.message,

                tool=finding.tool,

                fingerprint=finding.fingerprint,

                metadata=finding.metadata,
            )

            # ----------------------------------------------
            # AGENT 1
            # ----------------------------------------------

            classification = (
                await self.classification_agent.classify(
                    analysis_finding
                )
            )

            # ----------------------------------------------
            # AGENT 2
            # ----------------------------------------------

            estimation = (
                await self.estimation_agent.estimate(
                    analysis_finding,
                    classification
                )
            )

            # ----------------------------------------------
            # Build issue
            # ----------------------------------------------

            issue = {

                "finding_id":
                    analysis_finding.finding_id,

                "file_path":
                    analysis_finding.file_path,

                "line":
                    analysis_finding.line,

                "tool":
                    analysis_finding.tool,

                "rule_id":
                    analysis_finding.rule_id,

                "debt_type":
                    classification.debt_type,

                "impact":
                    classification.impact,

                "risk":
                    classification.risk,

                "estimated_minutes":
                    estimation.estimated_minutes,

                "confidence":
                    round(
                        (
                            classification.confidence
                            +
                            estimation.confidence
                        ) / 2,
                        2
                    ),

                "recommendation":
                    estimation.recommendation,

                "complexity":
                    classification.complexity,

                "reasoning":
                    estimation.reasoning,
            }

            issues.append(issue)

        # ====================================================
        # AGGREGATE ALL FINDINGS
        # ====================================================

        summary = self.aggregator.aggregate(
            issues
        )

        # ====================================================
        # COST
        # ====================================================

        estimated_cost = (
            self.cost_calculator.calculate(
                summary["total_debt_minutes"]
            )
        )

        # ====================================================
        # HEALTH
        # ====================================================

        health_score = (
            self.health_calculator.calculate(

                total_findings=
                    summary["total_findings"],

                critical=
                    summary["critical_issues"],

                high=
                    summary["high_risk_issues"],

                debt_hours=
                    summary["total_debt_hours"],

                lines_changed=
                    request.lines_changed,
            )
        )

        health_status = (
            self.health_calculator.status(
                health_score
            )
        )

        # ====================================================
        # DEBT RATIO
        # ====================================================

        debt_ratio = 0.0

        if request.lines_changed > 0:

            debt_ratio = round(
                summary["total_debt_minutes"]
                / request.lines_changed,
                4
            )

        # ====================================================
        # FINAL SUMMARY
        # ====================================================

        summary.update({

            "estimated_cost":
                estimated_cost,

            "debt_ratio":
                debt_ratio,

            "health_score":
                health_score,

            "health_status":
                health_status,
        })

        # ====================================================
        # CREATE ONE REVIEW
        # ====================================================

        review_data = {

            **summary,

            "repository":
                request.repository,

            "pull_request_number":
                request.pull_request_number,

            "commit_sha":
                request.commit_sha,
        }

        review = await (
            self.repository.create_review(
                review_data
            )
        )

        # ====================================================
        # CREATE MANY ISSUES
        # ====================================================

        for issue in issues:

            await self.repository.create_issue(
                review.id,
                issue
            )

        # ====================================================
        # COMMIT
        # ====================================================

        await self.session.commit()

        # ====================================================
        # RETURN
        # ====================================================

        return {

            "repository":
                request.repository,

            "pull_request_number":
                request.pull_request_number,

            "commit_sha":
                request.commit_sha,

            "summary":
                summary,

            "issues":
                issues,
        }