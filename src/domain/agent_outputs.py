from pydantic import BaseModel, Field


DEBT_TYPES = (
    "SECURITY", "BUG", "MAINTAINABILITY", "PERFORMANCE", "RELIABILITY",
    "DUPLICATION", "TESTABILITY", "ARCHITECTURE", "DOCUMENTATION",
)

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

COMPLEXITIES = ("LOW", "MEDIUM", "HIGH")

MIN_MINUTES, MAX_MINUTES = 1, 2400  # 1 minute .. 5 working days


class ClassificationOutput(BaseModel):

    debt_type: str

    impact: str

    risk: str

    complexity: str

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    reason: str


class EstimationOutput(BaseModel):

    estimated_minutes: int

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    recommendation: str

    reasoning: str
