from collections import defaultdict
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from .models import DebtIssue, DebtReview

_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _issue_sort_key(i: DebtIssue):
    return (_RISK_ORDER.get(i.risk, 4), -i.estimated_minutes)


def issue_to_dict(i: DebtIssue) -> dict:
    return {
        "id": str(i.id),
        "finding_id": str(i.finding_id),
        "file_path": i.file_path,
        "line": i.line,
        "tool": i.tool,
        "rule_id": i.rule_id,
        "debt_type": i.debt_type,
        "impact": i.impact,
        "risk": i.risk,
        "estimated_minutes": i.estimated_minutes,
        "confidence": _num(i.confidence),
        "recommendation": i.recommendation,
    }


def review_to_dict(r: DebtReview, with_issues: bool = False) -> dict:

    data = {
        "id": str(r.id),
        "repository": r.repository,
        "pull_request_number": r.pull_request_number,
        "commit_sha": r.commit_sha,
        "total_findings": r.total_findings,
        "total_debt_minutes": r.total_debt_minutes,
        "total_debt_hours": _num(r.total_debt_hours),
        "estimated_cost": _num(r.estimated_cost),
        "debt_ratio": _num(r.debt_ratio),
        "health_score": r.health_score,
        "health_status": r.health_status,
        "critical_issues": r.critical_issues,
        "high_risk_issues": r.high_risk_issues,
        "medium_risk_issues": r.medium_risk_issues,
        "low_risk_issues": r.low_risk_issues,
        "security_issues": r.security_issues,
        "bugs": r.bugs,
        "maintainability_issues": r.maintainability_issues,
        "created_at": r.created_at.isoformat(),
    }

    if with_issues:
        data["issues"] = [
            issue_to_dict(i) for i in sorted(r.issues, key=_issue_sort_key)
        ]

    return data


class DebtRepository:
    """debt_reviews / debt_issues in this service's own database."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def ping(self) -> None:
        async with self._sf() as s:
            await s.execute(select(1))

    async def save(self, result: dict) -> dict:
        """Persist a DebtService.calculate() result.

        Re-running the same repo + PR + commit replaces the earlier run (a
        redelivered event must not create duplicate history); a new commit on
        the PR adds a new row, which is what the trend series is built from.
        """

        s = result["summary"]

        review = DebtReview(
            repository=result["repository"],
            pull_request_number=result["pull_request_number"],
            commit_sha=result["commit_sha"],
            total_findings=s["total_findings"],
            total_debt_minutes=s["total_debt_minutes"],
            total_debt_hours=s["total_debt_hours"],
            estimated_cost=s["estimated_cost"],
            debt_ratio=s["debt_ratio"],
            health_score=s["health_score"],
            health_status=s["health_status"],
            critical_issues=s["critical_issues"],
            high_risk_issues=s["high_risk_issues"],
            medium_risk_issues=s["medium_risk_issues"],
            low_risk_issues=s["low_risk_issues"],
            security_issues=s["security_issues"],
            bugs=s["bugs"],
            maintainability_issues=s["maintainability_issues"],
            issues=[
                DebtIssue(
                    finding_id=i["finding_id"],
                    file_path=i["file_path"],
                    line=i["line"],
                    tool=i["tool"],
                    rule_id=i["rule_id"],
                    debt_type=i["debt_type"],
                    impact=i["impact"],
                    risk=i["risk"],
                    estimated_minutes=i["estimated_minutes"],
                    confidence=i["confidence"],
                    recommendation=i["recommendation"],
                )
                for i in result["issues"]
            ],
        )

        async with self._sf() as session, session.begin():

            await session.execute(
                delete(DebtReview).where(
                    DebtReview.repository == review.repository,
                    DebtReview.pull_request_number == review.pull_request_number,
                    DebtReview.commit_sha == review.commit_sha,
                )
            )

            session.add(review)

            await session.flush()

            await session.refresh(review, ["created_at"])

            return review_to_dict(review, with_issues=True)

    async def get_latest_for_pull_request(
        self,
        repository: str,
        pull_request_number: int
    ) -> dict | None:

        async with self._sf() as session:

            review = (
                await session.execute(
                    select(DebtReview)
                    .options(selectinload(DebtReview.issues))
                    .where(
                        DebtReview.repository == repository,
                        DebtReview.pull_request_number == pull_request_number,
                    )
                    .order_by(DebtReview.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            return review_to_dict(review, with_issues=True) if review else None

    async def list_reviews(self, repository: str, limit: int = 20) -> list[dict]:

        async with self._sf() as session:

            rows = (
                await session.execute(
                    select(DebtReview)
                    .where(DebtReview.repository == repository)
                    .order_by(DebtReview.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()

            return [review_to_dict(r) for r in rows]

    async def list_repositories(self) -> list[str]:

        async with self._sf() as session:

            rows = await session.execute(
                select(DebtReview.repository)
                .distinct()
                .order_by(DebtReview.repository)
            )

            return list(rows.scalars())

    async def repository_summary(
        self,
        repository: str,
        trend_limit: int = 30
    ) -> dict | None:
        """Everything the dashboard needs in one call: totals over the latest
        review of each PR, breakdowns, a per-PR table and a trend series."""

        async with self._sf() as session:

            latest_ids = (
                select(DebtReview.id)
                .where(DebtReview.repository == repository)
                .distinct(DebtReview.pull_request_number)
                .order_by(
                    DebtReview.pull_request_number,
                    DebtReview.created_at.desc(),
                )
            )

            latest = (
                await session.execute(
                    select(DebtReview)
                    .where(DebtReview.id.in_(latest_ids))
                    .order_by(DebtReview.created_at.desc())
                )
            ).scalars().all()

            if not latest:
                return None

            issues = (
                await session.execute(
                    select(DebtIssue).where(
                        DebtIssue.debt_review_id.in_([r.id for r in latest])
                    )
                )
            ).scalars().all()

            history = (
                await session.execute(
                    select(DebtReview)
                    .where(DebtReview.repository == repository)
                    .order_by(DebtReview.created_at.desc())
                    .limit(trend_limit)
                )
            ).scalars().all()

        by_type: dict[str, dict] = defaultdict(lambda: {"count": 0, "minutes": 0})

        for i in issues:
            by_type[i.debt_type]["count"] += 1
            by_type[i.debt_type]["minutes"] += i.estimated_minutes

        # Debt of the most recently calculated pull request (`latest` is
        # newest first), not a sum across PRs.
        total_minutes = latest[0].total_debt_minutes

        pr_by_id = {r.id: r.pull_request_number for r in latest}

        top = sorted(issues, key=_issue_sort_key)[:10]

        return {
            "repository": repository,
            "pull_requests_analyzed": len(latest),
            "total_findings": sum(r.total_findings for r in latest),
            "total_debt_minutes": total_minutes,
            "total_debt_hours": round(total_minutes / 60, 2),
            "estimated_cost": float(sum(r.estimated_cost or 0 for r in latest)),
            "average_health_score": round(
                sum(r.health_score for r in latest) / len(latest)
            ),
            "risk_counts": {
                "CRITICAL": sum(r.critical_issues for r in latest),
                "HIGH": sum(r.high_risk_issues for r in latest),
                "MEDIUM": sum(r.medium_risk_issues for r in latest),
                "LOW": sum(r.low_risk_issues for r in latest),
            },
            "by_type": [
                {"debt_type": k, **v}
                for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]["minutes"])
            ],
            "top_issues": [
                {**issue_to_dict(i), "pull_request_number": pr_by_id[i.debt_review_id]}
                for i in top
            ],
            "pull_requests": [review_to_dict(r) for r in latest],
            # oldest -> newest, for plotting left to right
            "trend": [
                {
                    "created_at": r.created_at.isoformat(),
                    "pull_request_number": r.pull_request_number,
                    "commit_sha": r.commit_sha,
                    "health_score": r.health_score,
                    "total_debt_minutes": r.total_debt_minutes,
                }
                for r in reversed(history)
            ],
        }
