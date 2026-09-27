import asyncio

from sqlalchemy import select

from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.models import DebtReview


async def test_read_reviews():

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(DebtReview)
        )

        reviews = result.scalars().all()

        print(f"Found {len(reviews)} debt reviews")

        for review in reviews:

            print("\n--------------------------")

            print("ID:", review.id)
            print("Repository:", review.repository)
            print(
                "Pull Request:",
                review.pull_request_number
            )
            print("Commit:", review.commit_sha)

            print(
                "Debt:",
                review.total_debt_hours,
                "hours"
            )

            print(
                "Cost:",
                review.estimated_cost
            )

            print(
                "Health:",
                review.health_score
            )

            print(
                "Status:",
                review.health_status
            )


if __name__ == "__main__":
    asyncio.run(test_read_reviews())