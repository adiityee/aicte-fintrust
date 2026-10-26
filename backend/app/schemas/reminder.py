from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.models.fdr import FDRStatus
from app.models.reminder import ReminderStatus, ReminderType


class ReminderAlertResponse(BaseModel):
    id: int
    fdr_id: int
    institution_id: int
    reminder_type: ReminderType
    days_offset: int
    due_date: date
    status: ReminderStatus
    message: Optional[str] = None
    recipient: Optional[str] = None
    assigned_officer_id: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReminderAcknowledgeRequest(BaseModel):
    actor_id: Optional[str] = "INSTITUTION_USER"


class CheckMaturityResponse(BaseModel):
    checked_at: str
    new_alerts_created: int
    escalated_alerts_count: int
    alerts: List[ReminderAlertResponse]


class EncashmentNoticeResponse(BaseModel):
    message: str
    fdr_id: int
    fdr_status: FDRStatus
    notice_reference: str
    notice_pdf_path: str
    officer_queue: str
