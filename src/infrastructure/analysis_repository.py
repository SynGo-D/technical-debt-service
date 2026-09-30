"""Read-only access to analysis-engine's database.

Only analysis-engine's `analysis_results` and `findings` tables are used
(see analysis-engine-service/src/analysis_engine/infrastructure/schema.py).
Nothing here writes.
"""
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.debt import DebtCalculationRequest
from ..domain.finding import AnalysisFinding

# Set by analysis-engine's diffing/change_mapper.py on every finding.
ON_CHANGED_LINE = "on_changed_line"


class AnalysisNotFound(Exception):

    def __init__(self, repository: str, pull_request_number: int):
        super().__init__(
            f"No completed analysis result for {repository} "
            f"PR #{pull_request_number} in the analysis-engine database."
        )


def _json(value) -> dict:
    # Depending on the driver codec, JSONB arrives as str or already parsed.
    if value is None:
        return {}
    if isinstance(value, (str, bytes)):
        return json.loads(value)
    return value


def introduced_findings(
    findings: list[AnalysisFinding],
    changes_available: bool,
) -> tuple[list[AnalysisFinding], str]:
    """The findings a PR is charged for, and the scope that describes them.

    analysis-engine lints the whole repository and tags each finding with
    whether the PR changed its line. A PR's debt is only what it introduced;
    without the diff (or the tag, from an older analysis-engine) we can't
    tell, so every finding is counted and the scope says so.
    """
    tagged = any(ON_CHANGED_LINE in f.metadata for f in findings)

    if changes_available and (tagged or not findings):
        return [f for f in findings if f.metadata.get(ON_CHANGED_LINE) is True], "pull_request"

    return findings, "repository"


class AnalysisEngineRepository:

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def ping(self) -> None:
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))

    async def get_calculation_request(
        self,
        repository: str,
        pull_request_number: int,
    ) -> DebtCalculationRequest:
        """Latest *completed* analysis of the PR, shaped as the input the
        technical-debt calculation expects."""

        async with self._session_factory() as session:

            result = (
                await session.execute(
                    text(
                        """
                        SELECT result_id, commit_sha, pull_request_changes
                        FROM analysis_results
                        WHERE repository = :repository
                          AND pull_request_number = :pr
                          AND status = 'completed'
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {"repository": repository, "pr": pull_request_number},
                )
            ).mappings().first()

            if result is None:
                raise AnalysisNotFound(repository, pull_request_number)

            rows = (
                await session.execute(
                    text(
                        """
                        SELECT finding_id, repository, pull_request_number,
                               commit_sha, file_path, line, col, severity,
                               category, rule_id, message, tool, fingerprint,
                               remediation_minutes, metadata
                        FROM findings
                        WHERE result_id = :result_id
                        ORDER BY file_path, line
                        """
                    ),
                    {"result_id": result["result_id"]},
                )
            ).mappings().all()

        findings = [
            AnalysisFinding(
                finding_id=r["finding_id"],
                repository=r["repository"],
                pull_request_number=r["pull_request_number"],
                commit_sha=r["commit_sha"],
                file_path=r["file_path"],
                line=r["line"],
                column=r["col"],
                severity=r["severity"],
                category=r["category"],
                rule_id=r["rule_id"],
                message=r["message"],
                tool=r["tool"],
                fingerprint=r["fingerprint"],
                remediation_minutes=r["remediation_minutes"],
                metadata=_json(r["metadata"]),
            )
            for r in rows
        ]

        # `pull_request_changes` is NULL for old results, or status
        # "unavailable" when the diff could not be computed: no line counts
        # then, and the debt ratio is simply not computed.
        changes = _json(result["pull_request_changes"])
        available = changes.get("status") == "available"

        introduced, scope = introduced_findings(findings, available)

        return DebtCalculationRequest(
            repository=repository,
            pull_request_number=pull_request_number,
            commit_sha=result["commit_sha"],
            findings=introduced,
            scope=scope,
            pre_existing_excluded=len(findings) - len(introduced),
            lines_added=changes.get("lines_added", 0) if available else 0,
            lines_removed=changes.get("lines_removed", 0) if available else 0,
            files_changed=changes.get("files_changed", 0) if available else 0,
        )
