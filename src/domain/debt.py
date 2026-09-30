from pydantic import BaseModel

from .finding import AnalysisFinding


class DebtCalculationRequest(BaseModel):

    repository: str

    pull_request_number: int

    commit_sha: str

    lines_added: int = 0

    lines_removed: int = 0

    files_changed: int = 0

    findings: list[AnalysisFinding]

    # "pull_request": only findings on lines the PR changed (debt it introduced).
    # "repository": the diff was unavailable, so every finding was counted.
    scope: str = "pull_request"

    # Findings left out because they sit on lines the PR did not change.
    pre_existing_excluded: int = 0