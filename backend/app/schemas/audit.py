from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    previous_hash: str
    current_hash: str
    action: str
    payload_hash: str
    user_id: Optional[str] = None
    timestamp: datetime
    details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuditTrailResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[AuditLogResponse]


class AuditVerifyResponse(BaseModel):
    valid: bool
    broken_at_id: Optional[int] = None
    total_records: int
    message: str
    broken_links: List[Dict[str, Any]] = []
    verified_at: str
