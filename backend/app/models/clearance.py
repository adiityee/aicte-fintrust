from datetime import datetime
import enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.fdr import FDR


class ClearanceCell(str, enum.Enum):
    """Clearance cells required for release gate as per architecture plan."""
    PGRC = "PGRC"
    VIGILANCE = "VIGILANCE"
    APPROVAL_BUREAU = "APPROVAL_BUREAU"
    LEGAL = "LEGAL"
    FINANCE = "FINANCE"


class ClearanceStatus(str, enum.Enum):
    """Status of an individual clearance cell task."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Clearance(Base):
    """
    Clearance Model
    Represents parallel clearance tasks created across configured cells
    prior to FDR release authorization.
    """
    __tablename__ = "clearances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    fdr_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fdrs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cell_name: Mapped[ClearanceCell] = mapped_column(
        Enum(ClearanceCell, name="clearance_cell_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    status: Mapped[ClearanceStatus] = mapped_column(
        Enum(ClearanceStatus, name="clearance_status_enum", native_enum=False),
        default=ClearanceStatus.PENDING,
        nullable=False,
        index=True,
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    officer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    fdr: Mapped["FDR"] = relationship(
        "FDR",
        back_populates="clearances",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Clearance(id={self.id}, fdr_id={self.fdr_id}, cell='{self.cell_name}', status='{self.status}')>"
