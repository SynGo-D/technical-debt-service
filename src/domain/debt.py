from pydantic import BaseModel

from .finding import AnalysisFinding


class DebtCalculationRequest(BaseModel):

    repository: str

    pull_request_number: int

    commit_sha: str

    findings: list[AnalysisFinding]

    lines_added: int = 0

    lines_removed: int = 0

    files_changed: int = 0