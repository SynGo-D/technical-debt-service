"""
Consuming analysis.completed.

Most of these are about NOT calculating. Each finding costs two LLM calls,
so the guards in front of the expensive part are the part most worth
pinning down — and the difference between acknowledging a message and
parking it decides whether a bad event is retried forever.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import settings
from src.infrastructure.analysis_repository import AnalysisNotFound
from src.messaging.consumer import AnalysisCompletedConsumer
from src.messaging.topology import (
    ANALYSIS_EXCHANGE_NAME,
    DEAD_ANALYSIS_EXCHANGE_NAME,
    DEBT_QUEUE_ARGUMENTS,
    DEBT_QUEUE_NAME,
    DEBT_ROUTING_PATTERN,
)


def _message(body) -> MagicMock:
    message = MagicMock()
    message.body = (json.dumps(body) if not isinstance(body, str) else body).encode()
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    return message


def _event(**overrides) -> dict:
    event = {
        "repository": "owner/repo",
        "pullRequestNumber": 7,
        "commitSha": "a" * 40,
        "findingsCount": 12,
        "status": "completed",
    }
    event.update(overrides)
    return event


def _consumer(*, already_costed=False, findings_error=None, calculate_error=None):
    debt_repository = MagicMock()
    debt_repository.exists_for_commit = AsyncMock(return_value=already_costed)
    debt_repository.save = AsyncMock(
        return_value={"total_debt_hours": 1.5, "total_findings": 12, "health_score": 80}
    )

    analysis_repository = MagicMock()
    analysis_repository.get_calculation_request = AsyncMock(
        side_effect=findings_error, return_value=MagicMock()
    )

    debt_service = MagicMock()
    debt_service.calculate = AsyncMock(side_effect=calculate_error, return_value={"x": 1})

    consumer = AnalysisCompletedConsumer(
        debt_service=debt_service,
        debt_repository=debt_repository,
        analysis_repository=analysis_repository,
    )
    return consumer, debt_service, debt_repository


@pytest.fixture(autouse=True)
def _auto_calculate_on(monkeypatch):
    monkeypatch.setattr(settings, "auto_calculate", True)
    monkeypatch.setattr(settings, "auto_calculate_max_findings", 400)


class TestTheHappyPath:
    async def test_a_completed_analysis_is_costed_and_acknowledged(self):
        consumer, debt_service, debt_repository = _consumer()
        message = _message(_event())

        await consumer._handle_message(message)

        debt_service.calculate.assert_awaited_once()
        debt_repository.save.assert_awaited_once()
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()


class TestGuardsBeforeSpendingMoney:
    async def test_a_commit_already_costed_is_skipped(self):
        consumer, debt_service, _ = _consumer(already_costed=True)
        message = _message(_event())

        await consumer._handle_message(message)

        debt_service.calculate.assert_not_awaited()
        message.ack.assert_awaited_once()

    async def test_auto_calculate_off_consumes_without_costing(self, monkeypatch):
        monkeypatch.setattr(settings, "auto_calculate", False)
        consumer, debt_service, debt_repository = _consumer()
        message = _message(_event())

        await consumer._handle_message(message)

        debt_service.calculate.assert_not_awaited()
        # Not even the existence check: the decision is made before it.
        debt_repository.exists_for_commit.assert_not_awaited()
        message.ack.assert_awaited_once()

    async def test_an_implausible_number_of_findings_is_skipped(self, monkeypatch):
        monkeypatch.setattr(settings, "auto_calculate_max_findings", 400)
        consumer, debt_service, _ = _consumer()

        await consumer._handle_message(_message(_event(findingsCount=5000)))

        debt_service.calculate.assert_not_awaited()

    async def test_the_ceiling_can_be_disabled_with_zero(self, monkeypatch):
        monkeypatch.setattr(settings, "auto_calculate_max_findings", 0)
        consumer, debt_service, _ = _consumer()

        await consumer._handle_message(_message(_event(findingsCount=5000)))

        debt_service.calculate.assert_awaited_once()


class TestBadEventsAreDiscardedNotRetried:
    async def test_a_body_that_is_not_json(self):
        consumer, debt_service, _ = _consumer()
        message = _message("not json at all")

        await consumer._handle_message(message)

        message.nack.assert_awaited_once_with(requeue=False)
        debt_service.calculate.assert_not_awaited()

    async def test_an_event_missing_the_repository(self):
        consumer, _, _ = _consumer()
        message = _message(_event(repository=None))

        await consumer._handle_message(message)

        message.nack.assert_awaited_once_with(requeue=False)

    async def test_a_pull_request_number_that_is_not_an_integer(self):
        consumer, debt_service, _ = _consumer()
        message = _message(_event(pullRequestNumber="seven"))

        await consumer._handle_message(message)

        message.nack.assert_awaited_once_with(requeue=False)
        debt_service.calculate.assert_not_awaited()

    async def test_an_analysis_that_does_not_exist(self):
        # The event promised findings the database does not have. A retry
        # cannot conjure them.
        consumer, _, _ = _consumer(findings_error=AnalysisNotFound("owner/repo", 7))
        message = _message(_event())

        await consumer._handle_message(message)

        message.nack.assert_awaited_once_with(requeue=False)


class TestFailuresWorthKeeping:
    async def test_an_unreadable_analysis_database_is_parked(self):
        consumer, _, _ = _consumer(findings_error=OSError("connection reset"))
        message = _message(_event())

        await consumer._handle_message(message)

        message.nack.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()

    async def test_a_failing_calculation_is_parked(self):
        consumer, _, _ = _consumer(calculate_error=RuntimeError("model unavailable"))
        message = _message(_event())

        await consumer._handle_message(message)

        message.nack.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()


class TestContractWithAnalysisEngine:
    def test_pins_the_values_the_other_service_must_match(self):
        # analysis-engine's messaging/topology.py declares the same
        # exchange and names the same queue and pattern. Queue arguments
        # are immutable in RabbitMQ, so if this changes without the
        # matching change there, whichever declares second crash-loops on
        # PRECONDITION_FAILED. If this fails, change both or neither.
        assert ANALYSIS_EXCHANGE_NAME == "analysis.events"
        assert DEBT_QUEUE_NAME == "debt_queue"
        assert DEBT_ROUTING_PATTERN == "analysis.completed.#"
        assert DEBT_QUEUE_ARGUMENTS == {
            "x-dead-letter-exchange": "analysis.events.dead"
        }

    def test_does_not_dead_letter_to_webhook_listeners_exchange(self):
        # pr_queue.dead is bound to webhook.events.dead under `pr.#`. A
        # dead-lettered debt event keeps its `analysis.completed.*` routing
        # key, which matches that binding, so parking it there would drop
        # it. This assertion exists to stop that being "simplified" back.
        assert DEAD_ANALYSIS_EXCHANGE_NAME != "webhook.events.dead"
        assert DEBT_QUEUE_ARGUMENTS["x-dead-letter-exchange"] != "webhook.events.dead"
