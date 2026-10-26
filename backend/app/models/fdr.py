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
    SUBMITTED = "SUBMITTED"
    UNDER_SCRUTINY = "UNDER_SCRUTINY"
    QUERY_RAISED = "QUERY_RAISED"
    BANK_VERIFICATION_PENDING = "BANK_VERIFICATION_PENDING"
    BANK_VERIFIED = "BANK_VERIFIED"
    ACTIVE = "ACTIVE"
    MATURED = "MATURED"
    RENEWED = "RENEWED"
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    CLEARANCES_APPROVED = "CLEARANCES_APPROVED"
    RELEASED = "RELEASED"
    ENCASHMENT_NOTICE_DRAFTED = "ENCASHMENT_NOTICE_DRAFTED"


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
    fdr_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    ifsc_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    principal_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    interest_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    lien_holder: Mapped[str] = mapped_column(String(255), default="AICTE", nullable=False)
    
    status: Mapped[FDRStatus] = mapped_column(
        Enum(FDRStatus, name="fdr_status_enum", native_enum=False),
        default=FDRStatus.DRAFT,
        nullable=False,
        index=True,
    )

    document_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

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
