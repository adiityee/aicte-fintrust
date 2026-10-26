from typing import List, Optional
from pydantic import BaseModel

from app.models.fdr import FDRStatus


class ClearanceCompletionSummary(BaseModel):
    cell_name: str
    status: str
    officer_id: Optional[str] = None
    completed_at: Optional[str] = None
    remarks: Optional[str] = None


class PublicVerificationResponse(BaseModel):
    fdr_id: int
    fdr_number: str
    institution_name: str
    aicte_permanent_id: str
    bank_name: str
    principal_amount: str
    fdr_status: FDRStatus
    is_released: bool
    is_signature_valid: bool
    signature_algorithm: str = "Ed25519 (RFC 8032)"
    ed25519_signature: Optional[str] = None
    public_key_hex: Optional[str] = None
    noc_document_path: Optional[str] = None
    noc_download_url: Optional[str] = None
    clearances: List[ClearanceCompletionSummary] = []
    verification_timestamp: str
    message: str
