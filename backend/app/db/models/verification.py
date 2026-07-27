from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class VerificationTask(TimestampMixin, Base):
    __tablename__ = "verification_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    match_result_id: Mapped[str] = mapped_column(ForeignKey("match_results.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("verification_tasks.id"),
        index=True,
        nullable=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="verification_tasks")
    match_result: Mapped["MatchResult"] = relationship(back_populates="verification_tasks")
    evidence: Mapped[list["VerificationEvidence"]] = relationship(
        back_populates="verification_task",
        cascade="all, delete-orphan",
    )


class VerificationEvidence(TimestampMixin, Base):
    __tablename__ = "verification_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    verification_task_id: Mapped[str] = mapped_column(
        ForeignKey("verification_tasks.id"),
        index=True,
    )
    match_result_id: Mapped[str] = mapped_column(ForeignKey("match_results.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    raw_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)

    verification_task: Mapped["VerificationTask"] = relationship(back_populates="evidence")
    match_result: Mapped["MatchResult"] = relationship(back_populates="verification_evidence")
