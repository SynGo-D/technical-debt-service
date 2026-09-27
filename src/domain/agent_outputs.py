from pydantic import BaseModel, Field


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