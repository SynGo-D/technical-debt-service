from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DebtReview(Base):

    __tablename__ = "debt_reviews"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    repository: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    pull_request_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    commit_sha: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    total_findings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_debt_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_debt_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    debt_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
    )

    health_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    health_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    critical_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    high_risk_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    medium_risk_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    low_risk_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    security_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    bugs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    maintainability_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    issues: Mapped[list["DebtIssue"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
    )


class DebtIssue(Base):

    __tablename__ = "debt_issues"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    debt_review_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "debt_reviews.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    finding_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    line: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    tool: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    rule_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    debt_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    impact: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    risk: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    estimated_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    recommendation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    review: Mapped["DebtReview"] = relationship(
        back_populates="issues",
    )