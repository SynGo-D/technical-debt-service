from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.database import get_db
from ..domain.finding import AnalysisFinding
from ..services.debt_service import DebtService


router = APIRouter(
    prefix="/api/debt",
    tags=["Technical Debt"]
)


class DebtRequest(BaseModel):

    finding_id: str

    repository: str

    pull_request_number: int

    commit_sha: str

    file_path: str

    line: int

    column: int | None = None

    severity: str

    category: str

    rule_id: str

    message: str

    tool: str

    fingerprint: str

    metadata: dict = Field(
        default_factory=dict
    )

    lines_changed: int = Field(
        default=0,
        ge=0
    )


@router.post("/calculate")
async def calculate_debt(
    request: DebtRequest,
    db: AsyncSession = Depends(get_db)
):

    # Convert API request into domain object

    finding = AnalysisFinding(
        finding_id=request.finding_id,

        repository=request.repository,

        pull_request_number=
            request.pull_request_number,

        commit_sha=request.commit_sha,

        file_path=request.file_path,

        line=request.line,

        column=request.column,

        severity=request.severity,

        category=request.category,

        rule_id=request.rule_id,

        message=request.message,

        tool=request.tool,

        fingerprint=request.fingerprint,

        metadata=request.metadata,
    )

    # Create debt service

    service = DebtService(db)

    # Run the complete pipeline

    result = await service.calculate_debt(
        finding=finding,
        lines_changed=request.lines_changed
    )

    return result