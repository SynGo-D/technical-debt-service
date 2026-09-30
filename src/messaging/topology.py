"""
RabbitMQ topology for this service.

Mirrors analysis-engine's src/analysis_engine/messaging/topology.py. The two
files describe one contract from two sides, and the constants below must
match it exactly — a test in each repository pins the literal values,
because queue arguments are immutable in RabbitMQ and a disagreement is not
something that settles itself: whichever service declares second gets
PRECONDITION_FAILED and crash-loops on startup.
"""

# The exchange analysis-engine publishes finished analyses to. Declared on
# both sides with identical parameters, so it does not matter which starts
# first — but the type and durability must agree, for the same reason the
# queue arguments must.
ANALYSIS_EXCHANGE_NAME = "analysis.events"

# analysis.completed.github, analysis.completed.gitlab, ...
DEBT_ROUTING_PATTERN = "analysis.completed.#"

DEBT_QUEUE_NAME = "debt_queue"

# Failures are parked, not discarded. Debt calculation spends real money per
# finding, so a run that fails for a reason worth fixing is worth being able
# to find and replay rather than losing to a log line.
#
# A dedicated dead-letter exchange, NOT webhook-listener's
# webhook.events.dead. A dead-lettered message keeps its original routing
# key, so an `analysis.completed.github` event sent to that exchange would
# match its `pr.#` binding, go nowhere, and be dropped by the mechanism
# meant to preserve it.
DEAD_ANALYSIS_EXCHANGE_NAME = "analysis.events.dead"
DEAD_DEBT_QUEUE_NAME = "debt_queue.dead"

# A sink binds `#`: an unroutable parked message is no better than a
# discarded one.
DEAD_DEBT_ROUTING_PATTERN = "#"

# Fourteen days, matching pr_queue.dead. The broker's volume shares the
# host's disk and an unbounded queue of failures is its own outage; expiry
# IS the retention policy here rather than an oversight.
DEAD_DEBT_QUEUE_ARGUMENTS: dict[str, int] = {
    "x-message-ttl": 14 * 24 * 60 * 60 * 1000,
}

DEBT_QUEUE_ARGUMENTS: dict[str, str] = {
    "x-dead-letter-exchange": DEAD_ANALYSIS_EXCHANGE_NAME,
}
