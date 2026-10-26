from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.models.clearance import ClearanceCell, ClearanceStatus
from app.models.fdr import FDRStatus


class ClearanceResponse(BaseModel):
    id: int
    fdr_id: int
    cell_name: ClearanceCell
    status: ClearanceStatus
    remarks: Optional[str] = None
    officer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClearanceActionRequest(BaseModel):
    status: ClearanceStatus
    remarks: Optional[str] = None
    officer_id: Optional[str] = "SYSTEM_OFFICER"


class ReleaseRequestResponse(BaseModel):
    message: str
    fdr_id: int
    fdr_status: FDRStatus
    clearances: List[ClearanceResponse]


class ClearanceActionResponse(BaseModel):
    message: str
    task: ClearanceResponse
    fdr_status: FDRStatus
    all_cells_approved: bool


class ReleaseApprovalResponse(BaseModel):
    message: str
    fdr_id: int
    fdr_status: FDRStatus
    noc_document_path: str
    noc_download_url: str
    ed25519_signature: str
    public_verification_url: str
    authorized_by: str
    authorized_at: str
