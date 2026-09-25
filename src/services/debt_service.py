import asyncio

from technical_debt.agents.classification_agent import DebtClassificationAgent
from technical_debt.agents.estimation_agent import DebtEstimationAgent


class DebtService:

    def __init__(self):
        self.classification_agent = DebtClassificationAgent()
        self.estimation_agent = DebtEstimationAgent()

    async def process_findings(self, findings):

        semaphore = asyncio.Semaphore(5)

        async def process_finding(finding):

            async with semaphore:

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

                return classification, estimation

        results = await asyncio.gather(
            *[
                process_finding(finding)
                for finding in findings
            ]
        )

        return results