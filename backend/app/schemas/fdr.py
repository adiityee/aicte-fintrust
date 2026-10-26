from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.fdr import FDRStatus
from app.schemas.clearance import ClearanceResponse
from app.schemas.provenance import ProvenanceResponse


class FDRDraftRequest(BaseModel):
    """Payload to create or update a draft FDR."""
    id: Optional[int] = None
    institution_id: int
    fdr_number: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    principal_amount: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    issue_date: Optional[date] = None
    maturity_date: Optional[date] = None
    lien_holder: Optional[str] = "AICTE"
    document_path: Optional[str] = None


class FDRResponse(BaseModel):
    """Complete FDR response representation."""
    id: int
    institution_id: int
    fdr_number: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    principal_amount: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    issue_date: Optional[date] = None
    maturity_date: Optional[date] = None
    lien_holder: str
    status: FDRStatus
    document_path: Optional[str] = None
    document_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    provenance_records: List[ProvenanceResponse] = Field(default_factory=list)
    clearances: List[ClearanceResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FDRSubmitResponse(BaseModel):
    """Response returned upon successful submission."""
    message: str
    fdr: FDRResponse
    audit_hash: str


class FDRUploadDocumentResponse(BaseModel):
    """Response returned upon document upload."""
    message: str
    fdr_id: int
    document_path: str
    document_hash: str
    file_size_bytes: int


class FDRDocumentUrlResponse(BaseModel):
    """Response with presigned document URL."""
    fdr_id: int
    document_path: str
    presigned_url: str
    expires_in_seconds: int
