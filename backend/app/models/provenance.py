from datetime import datetime
import enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.fdr import FDR


class ProvenanceSourceType(str, enum.Enum):
    """Provenance source tiers as per PS requirement."""
    INSTITUTION_ENTERED = "INSTITUTION_ENTERED"
    OCR_EXTRACTED = "OCR_EXTRACTED"
    OFFICER_VERIFIED = "OFFICER_VERIFIED"
    BANK_CONFIRMED = "BANK_CONFIRMED"


class Provenance(Base):
    """
    Field Provenance Model
    Tracks the source tag and verification confidence of every field on an FDR.
    Enables UI badges (grey for self-declared, amber for OCR, green for bank-confirmed).
    """
    __tablename__ = "field_provenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    fdr_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fdrs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[ProvenanceSourceType] = mapped_column(
        Enum(ProvenanceSourceType, name="provenance_source_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extracted_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    fdr: Mapped["FDR"] = relationship(
        "FDR",
        back_populates="provenance_records",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Provenance(fdr_id={self.fdr_id}, field='{self.field_name}', source='{self.source_type}', score={self.confidence_score})>"
