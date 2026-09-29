from typing import Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from .infrastructure.database import get_db
from .services.debt_service import DebtService


app = FastAPI(
    title="Technical Debt Service",
    description="Multi-agent technical debt calculation service",
    version="1.0.0",
)


# ============================================================
# FINDING
# ============================================================

class FindingRequest(BaseModel):

    finding_id: str

    file_path: str
    line: int | None = None
    column: int | None = None

    severity: str
    category: str
    rule_id: str
    message: str
    tool: str

    fingerprint: str

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


# ============================================================
# PR REQUEST
# ============================================================

class DebtCalculationRequest(BaseModel):

    repository: str

    pull_request_number: int

    commit_sha: str

    lines_changed: int = Field(
        default=0,
        ge=0
    )

    findings: list[FindingRequest]


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "service": "Technical Debt Service",
        "status": "running",
    }


# ============================================================
# CALCULATE TECHNICAL DEBT
# ============================================================

@app.post("/api/debt/calculate")
async def calculate_debt(
    request: DebtCalculationRequest,
    session: AsyncSession = Depends(get_db),
):

    service = DebtService(session)

    result = await service.calculate_debt(
        request
    )

    return result