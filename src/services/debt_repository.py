from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.models import DebtReview, DebtIssue


class DebtRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------
    # CREATE REVIEW
    # ---------------------------------------------------------
    async def create_review(self, review_data: dict) -> DebtReview:
        review = DebtReview(
            repository=review_data["repository"],
            pull_request_number=review_data.get("pull_request_number"),
            commit_sha=review_data.get("commit_sha"),

            total_findings=review_data.get("total_findings", 0),
            total_debt_minutes=review_data.get("total_debt_minutes", 0),
            total_debt_hours=review_data.get("total_debt_hours", 0),

            estimated_cost=review_data.get("estimated_cost", 0),
            debt_ratio=review_data.get("debt_ratio", 0),

            health_score=review_data.get("health_score", 0),
            health_status=review_data.get("health_status", "GOOD"),

            critical_issues=review_data.get("critical_issues", 0),
            high_risk_issues=review_data.get("high_risk_issues", 0),
            medium_risk_issues=review_data.get("medium_risk_issues", 0),
            low_risk_issues=review_data.get("low_risk_issues", 0),

            security_issues=review_data.get("security_issues", 0),
            bugs=review_data.get("bugs", 0),
            maintainability_issues=review_data.get(
                "maintainability_issues", 0
            ),
        )

        self.session.add(review)

        await self.session.flush()

        return review

    # ---------------------------------------------------------
    # CREATE ISSUE
    # ---------------------------------------------------------
    async def create_issue(
        self,
        review_id: UUID,
        issue_data: dict
    ) -> DebtIssue:

        issue = DebtIssue(
            debt_review_id=review_id,

            finding_id=issue_data["finding_id"],
            file_path=issue_data["file_path"],
            line=issue_data.get("line"),

            tool=issue_data["tool"],
            rule_id=issue_data.get("rule_id"),

            debt_type=issue_data["debt_type"],
            impact=issue_data["impact"],
            risk=issue_data["risk"],

            estimated_minutes=issue_data.get(
                "estimated_minutes", 0
            ),

            confidence=issue_data.get("confidence", 0),

            recommendation=issue_data.get("recommendation"),
        )

        self.session.add(issue)

        await self.session.flush()

        return issue

    # ---------------------------------------------------------
    # GET REVIEW
    # ---------------------------------------------------------
    async def get_review(
        self,
        review_id: UUID
    ) -> DebtReview | None:

        result = await self.session.execute(
            select(DebtReview)
            .where(DebtReview.id == review_id)
        )

        return result.scalar_one_or_none()

    # ---------------------------------------------------------
    # GET ISSUES FOR A REVIEW
    # ---------------------------------------------------------
    async def get_review_issues(
        self,
        review_id: UUID
    ) -> list[DebtIssue]:

        result = await self.session.execute(
            select(DebtIssue)
            .where(DebtIssue.debt_review_id == review_id)
            .order_by(DebtIssue.created_at)
        )

        return list(result.scalars().all())

    # ---------------------------------------------------------
    # GET REPOSITORY HISTORY
    # ---------------------------------------------------------
    async def get_repository_history(
        self,
        repository: str
    ) -> list[DebtReview]:

        result = await self.session.execute(
            select(DebtReview)
            .where(DebtReview.repository == repository)
            .order_by(DebtReview.created_at.desc())
        )

        return list(result.scalars().all())