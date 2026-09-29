import asyncio

from sqlalchemy import select

from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.models import DebtReview, DebtIssue


async def main():

    async with AsyncSessionLocal() as session:

        print("\n========== DEBT REVIEWS ==========\n")

        result = await session.execute(
            select(DebtReview)
        )

        reviews = result.scalars().all()

        for review in reviews:

            print(
                f"ID: {review.id}"
            )

            print(
                f"Repository: {review.repository}"
            )

            print(
                f"PR: {review.pull_request_number}"
            )

            print(
                f"Debt: {review.total_debt_hours} hours"
            )

            print(
                f"Cost: ${review.estimated_cost}"
            )

            print(
                f"Health: {review.health_score}"
            )

            print("--------------------------------")

        print(
            f"\nTotal reviews: {len(reviews)}"
        )

        print("\n========== DEBT ISSUES ==========\n")

        result = await session.execute(
            select(DebtIssue)
        )

        issues = result.scalars().all()

        for issue in issues:

            print(
                f"Finding ID: {issue.finding_id}"
            )

            print(
                f"File: {issue.file_path}"
            )

            print(
                f"Tool: {issue.tool}"
            )

            print(
                f"Debt Type: {issue.debt_type}"
            )

            print(
                f"Risk: {issue.risk}"
            )

            print(
                f"Minutes: {issue.estimated_minutes}"
            )

            print("--------------------------------")

        print(
            f"\nTotal issues: {len(issues)}"
        )


if __name__ == "__main__":

    asyncio.run(main())