from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractedFieldItem(BaseModel):
    """Details of a single field extracted via Pass 1 text/OCR processing."""
    field_name: str
    extracted_value: Optional[str] = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_snippet: Optional[str] = None
    needs_human_review: bool = False


class TamperIndicatorItem(BaseModel):
    """Forensic flag indicating potential file manipulation (Flag only, never 'Fraud')."""
    indicator_code: str
    description: str
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    details: Optional[Dict[str, Any]] = None


class DuplicateCheckResult(BaseModel):
    """Result of duplicate file and FDR number cross-institution reuse checks."""
    is_duplicate_hash: bool = False
    duplicate_fdr_id: Optional[int] = None
    is_cross_institution_reuse: bool = False
    reused_fdr_id: Optional[int] = None
    reused_institution_id: Optional[int] = None
    message: Optional[str] = None


class DiscrepancyFieldComparison(BaseModel):
    """Side-by-side comparison between submitted form value and extracted document value."""
    field_name: str
    submitted_value: Optional[str] = None
    extracted_value: Optional[str] = None
    is_mismatch: bool = False
    severity: str = "MATCH"  # MATCH, CRITICAL, WARNING, INFO
    confidence_score: float = 0.0
    provenance_tier: str = "INSTITUTION_ENTERED"
    badge_color: str = "grey"  # grey (self-declared), amber (OCR), green (verified/confirmed), red (mismatch)
    highlight_snippet: Optional[str] = None


class OCRExtractionResponse(BaseModel):
    """Response returned by the Pass 1 extraction and forensics engine."""
    fdr_id: int
    extracted_fields: Dict[str, ExtractedFieldItem]
    tamper_indicators: List[TamperIndicatorItem]
    duplicate_check: DuplicateCheckResult
    needs_human_review: bool
    text_length: int
    page_count: int
    ocr_status: str


class DiscrepancyReportResponse(BaseModel):
    """Response returned by Pass 2 side-by-side discrepancy validation."""
    fdr_id: int
    has_discrepancies: bool
    discrepancy_count: int
    critical_count: int
    fields: Dict[str, DiscrepancyFieldComparison]
    tamper_indicators: List[TamperIndicatorItem]
    duplicate_warning: Optional[str] = None
    recommended_action: str


class FieldVerificationRequest(BaseModel):
    """Request by a scrutiny officer to accept or correct an extracted field."""
    field_name: str
    accepted_value: str
    officer_id: str
    remarks: Optional[str] = None


class FieldVerificationResponse(BaseModel):
    """Response returned upon officer field verification."""
    message: str
    fdr_id: int
    field_name: str
    verified_value: str
    provenance_source: str
    audit_hash: str
