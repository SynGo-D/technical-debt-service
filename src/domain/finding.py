from pydantic import BaseModel, Field


class AnalysisFinding(BaseModel):

    finding_id: str

    repository: str

    pull_request_number: int

    commit_sha: str

    file_path: str

    line: int | None = None

    column: int | None = None

    severity: str

    category: str

    rule_id: str

    message: str

    tool: str

    fingerprint: str

    remediation_minutes: int | None = None

    metadata: dict = Field(default_factory=dict)