from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class MatchResult(TimestampMixin, Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint(
            "vulnerability_id",
            "asset_id",
            name="uq_match_results_vulnerability_asset",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    risk_code: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
        index=True,
    )
    risk_entered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    vulnerability_id: Mapped[str] = mapped_column(ForeignKey("vulnerabilities.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="needs_review")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_priority: Mapped[str] = mapped_column(String(32), default="none")
    risk_model_version: Mapped[str] = mapped_column(String(32), default="risk-v1")
    risk_factors_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    risk_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    handling_status: Mapped[str] = mapped_column(
        String(32),
        default="unprocessed",
        index=True,
    )
    handling_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handling_updated_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    handling_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    handling_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_version: Mapped[str] = mapped_column(String(32), default="v1")
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=True,
    )

    vulnerability: Mapped["Vulnerability"] = relationship(back_populates="match_results")
    asset: Mapped["Asset"] = relationship(back_populates="match_results")
    evidence: Mapped[list["MatchEvidence"]] = relationship(
        back_populates="match_result",
        cascade="all, delete-orphan",
    )
    verification_tasks: Mapped[list["VerificationTask"]] = relationship(
        back_populates="match_result"
    )
    verification_evidence: Mapped[list["VerificationEvidence"]] = relationship(
        back_populates="match_result"
    )
    handling_records: Mapped[list["MatchResultHandlingRecord"]] = relationship(
        back_populates="match_result",
        cascade="all, delete-orphan",
    )
    risk_queue_events: Mapped[list["RiskQueueEvent"]] = relationship(
        back_populates="match_result",
        cascade="all, delete-orphan",
        order_by="RiskQueueEvent.created_at",
    )


class RiskCodeCounter(Base):
    __tablename__ = "risk_code_counters"

    code_date: Mapped[date] = mapped_column(Date, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False)


class MatchEvidence(TimestampMixin, Base):
    __tablename__ = "match_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    match_result_id: Mapped[str] = mapped_column(ForeignKey("match_results.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    raw_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)

    match_result: Mapped["MatchResult"] = relationship(back_populates="evidence")


class MatchResultHandlingRecord(TimestampMixin, Base):
    __tablename__ = "match_result_handling_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    match_result_id: Mapped[str] = mapped_column(
        ForeignKey("match_results.id", ondelete="CASCADE"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32), default="status_changed", index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    actor_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    match_result: Mapped["MatchResult"] = relationship(back_populates="handling_records")


class RiskQueueEvent(TimestampMixin, Base):
    __tablename__ = "risk_queue_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('entered', 'exited')",
            name="ck_risk_queue_events_event_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    match_result_id: Mapped[str] = mapped_column(
        ForeignKey("match_results.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(16), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    match_result: Mapped["MatchResult"] = relationship(back_populates="risk_queue_events")
