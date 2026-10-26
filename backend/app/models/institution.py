from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.fdr import FDR


class Institution(Base):
    """
    Institution Model
    Represents an AICTE-approved educational institution.
    """
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aicte_permanent_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

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
    fdrs: Mapped[List["FDR"]] = relationship(
        "FDR",
        back_populates="institution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Institution(id={self.id}, aicte_id='{self.aicte_permanent_id}', name='{self.name}')>"
