"""
Calculating debt when an analysis finishes, rather than when someone asks.

analysis-engine publishes analysis.completed.<provider> once a pull
request's findings are in its database. This consumer turns that into a debt
review, using exactly the same path as the HTTP "Calculate Debt" endpoint —
read the findings for that repository and pull request, run both agents,
store the result. The button still works and still does the same thing; it
is simply no longer the only way in.

Two guards stand in front of the expensive part, because each finding costs
two LLM calls:

  • A commit already costed is skipped. Redelivery is normal in RabbitMQ,
    and without this a requeue pays for the same answer twice.
  • A pull request with an implausible number of findings is skipped and
    logged rather than costed. One generated file can carry thousands.

A message is acknowledged whenever the outcome is settled — calculated,
skipped, or unusable. It is only parked when a retry might genuinely
succeed, which in practice means the databases or the model were briefly
unavailable.
"""
import json
import logging

from aio_pika import IncomingMessage
from aio_pika.abc import AbstractRobustChannel

from ..config import settings
from ..infrastructure.analysis_repository import AnalysisNotFound
from .topology import (
    ANALYSIS_EXCHANGE_NAME,
    DEAD_ANALYSIS_EXCHANGE_NAME,
    DEAD_DEBT_QUEUE_ARGUMENTS,
    DEAD_DEBT_QUEUE_NAME,
    DEAD_DEBT_ROUTING_PATTERN,
    DEBT_QUEUE_ARGUMENTS,
    DEBT_QUEUE_NAME,
    DEBT_ROUTING_PATTERN,
)

logger = logging.getLogger(__name__)


class AnalysisCompletedConsumer:
    """Consumes analysis.completed events and calculates debt for each."""

    def __init__(self, debt_service, debt_repository, analysis_repository):
        self._debt_service = debt_service
        self._debt_repository = debt_repository
        self._analysis_repository = analysis_repository

    async def start(self, channel: AbstractRobustChannel) -> None:
        # One at a time. Debt calculation is slow and spends money per
        # finding; a prefetch that let this service pull a dozen pull
        # requests at once would multiply both without making anything
        # finish sooner.
        await channel.set_qos(prefetch_count=1)

        # Declared with the same parameters analysis-engine uses, so it
        # does not matter which service reaches the broker first.
        exchange = await channel.declare_exchange(
            ANALYSIS_EXCHANGE_NAME, type="topic", durable=True
        )

        # The dead-letter path FIRST, before the queue that names it.
        # RabbitMQ does not validate x-dead-letter-exchange at declaration
        # time: a queue pointing at an exchange that does not exist yet
        # accepts the argument and then silently drops everything it tries
        # to park. Declaring the sink before the queue is what makes the
        # dead-letter argument mean anything.
        dead_exchange = await channel.declare_exchange(
            DEAD_ANALYSIS_EXCHANGE_NAME, type="topic", durable=True
        )
        dead_queue = await channel.declare_queue(
            DEAD_DEBT_QUEUE_NAME, durable=True, arguments=dict(DEAD_DEBT_QUEUE_ARGUMENTS)
        )
        await dead_queue.bind(dead_exchange, routing_key=DEAD_DEBT_ROUTING_PATTERN)

        queue = await channel.declare_queue(
            DEBT_QUEUE_NAME, durable=True, arguments=dict(DEBT_QUEUE_ARGUMENTS)
        )
        await queue.bind(exchange, routing_key=DEBT_ROUTING_PATTERN)

        await queue.consume(self._handle_message)
        logger.info(
            "Consuming %s from %s (%s), auto-calculate %s",
            DEBT_ROUTING_PATTERN, DEBT_QUEUE_NAME, ANALYSIS_EXCHANGE_NAME,
            "on" if settings.auto_calculate else "off",
        )

    async def _handle_message(self, message: IncomingMessage) -> None:
        try:
            event = json.loads(message.body)
        except json.JSONDecodeError as error:
            logger.error("discarding a message that is not JSON: %s", error)
            await message.nack(requeue=False)
            return

        repository = event.get("repository")
        pull_request_number = event.get("pullRequestNumber")
        commit_sha = event.get("commitSha") or ""
        findings_count = event.get("findingsCount")

        if not repository or not isinstance(pull_request_number, int):
            logger.error(
                "discarding an event without a usable repository and pull request number: %r",
                {k: event.get(k) for k in ("repository", "pullRequestNumber")},
            )
            await message.nack(requeue=False)
            return

        label = f"{repository} PR #{pull_request_number}"

        if not settings.auto_calculate:
            logger.info("%s: auto-calculate is off, not costing it", label)
            await message.ack()
            return

        ceiling = settings.auto_calculate_max_findings
        if ceiling and isinstance(findings_count, int) and findings_count > ceiling:
            logger.warning(
                "%s: %d findings is above the ceiling of %d, skipping. "
                "Calculate it by hand if it is genuinely wanted.",
                label, findings_count, ceiling,
            )
            await message.ack()
            return

        try:
            if commit_sha and await self._debt_repository.exists_for_commit(
                repository, pull_request_number, commit_sha
            ):
                logger.info("%s: %s already costed, skipping", label, commit_sha[:12])
                await message.ack()
                return

            payload = await self._analysis_repository.get_calculation_request(
                repository, pull_request_number
            )

        except AnalysisNotFound:
            # The event said there was an analysis and the database says
            # there is not. Retrying will not change that.
            logger.warning("%s: no completed analysis to cost, discarding", label)
            await message.nack(requeue=False)
            return

        except Exception as error:
            # A database that is briefly unreachable is exactly the case
            # worth keeping, so this one parks rather than discards.
            logger.exception("%s: could not read the analysis, parking: %s", label, error)
            await message.nack(requeue=False)
            return

        try:
            result = await self._debt_service.calculate(payload)
            saved = await self._debt_repository.save(result)

            logger.info(
                "%s: %s hours of debt across %d finding(s), health %s",
                label, saved.get("total_debt_hours"), saved.get("total_findings"),
                saved.get("health_score"),
            )
            await message.ack()

        except Exception as error:
            logger.exception("%s: debt calculation failed, parking: %s", label, error)
            await message.nack(requeue=False)
