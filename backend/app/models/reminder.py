from datetime import date, datetime, timezone
import enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.fdr import FDR
    from app.models.institution import Institution


class ReminderType(str, enum.Enum):
    UPCOMING_MATURITY = "UPCOMING_MATURITY"
    OVERDUE_REPLACEMENT = "OVERDUE_REPLACEMENT"
    PENDING_CLEARANCE = "PENDING_CLEARANCE"


class ReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED = "ESCALATED"


class ReminderAlert(Base):
    """
    Reminder Alert Model
    Tracks proactive deadline notifications, unacknowledged escalations,
    and renewal reminders for FDR instruments.
    """
    __tablename__ = "reminder_alerts"
    __table_args__ = (
        UniqueConstraint("fdr_id", "reminder_type", "days_offset", name="uq_fdr_reminder_offset"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    fdr_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fdrs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    institution_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_type: Mapped[ReminderType] = mapped_column(
        Enum(ReminderType, name="reminder_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    days_offset: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminder_status_enum", native_enum=False),
        default=ReminderStatus.PENDING,
        nullable=False,
        index=True,
    )

    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    fdr: Mapped["FDR"] = relationship("FDR", lazy="joined")
    institution: Mapped["Institution"] = relationship("Institution", lazy="joined")

    def __repr__(self) -> str:
        return f"<ReminderAlert(id={self.id}, fdr_id={self.fdr_id}, type={self.reminder_type}, offset={self.days_offset}, status={self.status})>"
