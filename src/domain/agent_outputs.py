from typing import Literal

from pydantic import BaseModel, Field


class DebtClassification(BaseModel):
    debt_type: Literal[
        "BUG",
        "SECURITY",
        "MAINTAINABILITY",
        "PERFORMANCE",
        "DUPLICATION",
        "COMPLEXITY",
        "CODE_STYLE",
        "OTHER",
    ]

    impact: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    ]

    risk: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    ]

    complexity: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
    ]

    confidence: float = Field(
        ge=0,
        le=1,
    )

    reason: str


class EffortEstimation(BaseModel):
    estimated_minutes: int = Field(
        ge=1,
        le=10000,
    )

    confidence: float = Field(
        ge=0,
        le=1,
    )

    recommendation: str

    reasoning: str