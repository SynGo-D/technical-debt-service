from pydantic import BaseModel, Field
from uuid import UUID


class AnalysisFinding(BaseModel):

    finding_id: UUID

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

    metadata: dict = Field(default_factory=dict)

    