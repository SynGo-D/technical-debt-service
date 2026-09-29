async def get_debt_input(
    self,
    repository: str,
    pull_request_number: int,
) -> dict | None:

    async with self._pool.acquire() as conn:

        result = await conn.fetchrow(
            """
            SELECT
                result_id,
                repository,
                pull_request_number,
                commit_sha
            FROM analysis_results
            WHERE repository = $1
              AND pull_request_number = $2
              AND status = 'completed'
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            repository,
            pull_request_number,
        )

        if result is None:
            return None

        findings = await conn.fetch(
            """
            SELECT
                finding_id,
                result_id,
                repository,
                pull_request_number,
                commit_sha,
                file_path,
                line,
                tool,
                rule_id,
                severity,
                category,
                message,
                fingerprint
            FROM findings
            WHERE result_id = $1
            ORDER BY file_path, line;
            """,
            result["result_id"],
        )

        return {
            "repository": result["repository"],
            "pull_request_number": result["pull_request_number"],
            "commit_sha": result["commit_sha"],
            "findings": [
                dict(row)
                for row in findings
            ],
        }