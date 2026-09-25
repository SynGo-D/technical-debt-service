from pydantic import BaseModel

from .finding import AnalysisFinding


from pydantic import BaseModel


class TechnicalDebtResult(BaseModel):
    repository: str
    pull_request_number: int
    commit_sha: str

    total_findings: int
    total_debt_minutes: int
    total_debt_hours: float
    estimated_cost: float
    debt_ratio: float | None

    health_score: int
    health_status: str

    critical_issues: int
    high_risk_issues: int
    medium_risk_issues: int
    security_issues: int
    bugs: int
    maintainability_issues: int

    issues: list[dict]