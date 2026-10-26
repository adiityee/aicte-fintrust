from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """
    Audit Log Model (Tamper-Evident Hash Chain)
    Stores an immutable ledger of all system mutations where:
    H_n = SHA256(H_{n-1} + action + payload_hash + user_id + timestamp)
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', current_hash='{self.current_hash[:8]}...')>"
