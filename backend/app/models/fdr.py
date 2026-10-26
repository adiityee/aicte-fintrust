from datetime import date, datetime
from decimal import Decimal
import enum
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.provenance import Provenance
    from app.models.clearance import Clearance


class FDRStatus(str, enum.Enum):
    """FDR lifecycle statuses as per architecture plan."""
    DRAFT = "DRAFT"
    UNDER_SCRUTINY = "UNDER_SCRUTINY"
    BANK_VERIFIED = "BANK_VERIFIED"
    ACTIVE = "ACTIVE"
    MATURED = "MATURED"
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    RELEASED = "RELEASED"


class FDR(Base):
    """
    Fixed Deposit Receipt (FDR) Model
    Represents the security deposit instrument deposited with AICTE as lien holder.
    """
    __tablename__ = "fdrs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    institution_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fdr_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ifsc_code: Mapped[str] = mapped_column(String(20), nullable=False)
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    lien_holder: Mapped[str] = mapped_column(String(255), default="AICTE", nullable=False)
    
    status: Mapped[FDRStatus] = mapped_column(
        Enum(FDRStatus, name="fdr_status_enum", native_enum=False),
        default=FDRStatus.DRAFT,
        nullable=False,
        index=True,
    )

    document_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

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
    institution: Mapped["Institution"] = relationship(
        "Institution",
        back_populates="fdrs",
        lazy="joined",
    )
    provenance_records: Mapped[List["Provenance"]] = relationship(
        "Provenance",
        back_populates="fdr",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    clearances: Mapped[List["Clearance"]] = relationship(
        "Clearance",
        back_populates="fdr",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<FDR(id={self.id}, fdr_number='{self.fdr_number}', bank='{self.bank_name}', status='{self.status}')>"
