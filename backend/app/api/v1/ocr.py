import hashlib
import json
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.fdr import FDR
from app.models.provenance import Provenance, ProvenanceSourceType
from app.schemas.ocr import (
    DiscrepancyReportResponse,
    ExtractedFieldItem,
    FieldVerificationRequest,
    FieldVerificationResponse,
    OCRExtractionResponse,
    TamperIndicatorItem,
)
from app.services.ocr_service import OCRService
from app.services.storage_service import storage_service

router = APIRouter()


async def get_fdr_with_relations(session: AsyncSession, fdr_id: int) -> Optional[FDR]:
    """Helper to load FDR with provenance and institution relations."""
    stmt = (
        select(FDR)
        .where(FDR.id == fdr_id)
        .options(
            selectinload(FDR.provenance_records),
            selectinload(FDR.clearances),
            selectinload(FDR.institution),
        )
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


@router.post("/{fdr_id}/process", response_model=OCRExtractionResponse, status_code=status.HTTP_200_OK)
async def process_fdr_ocr(
    fdr_id: int,
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Pass 1 Extraction & Forensics Pipeline:
    - Extracts PDF text layer with PyMuPDF and detects key FDR fields with confidence scores.
    - Inspects %%EOF markers for multiple incremental revisions (pikepdf).
    - Checks Producer/Creator metadata for third-party graphics/editing tools.
    - Checks duplicate file SHA-256 hashes and cross-institution instrument reuse.
    - Updates FDR record with tamper indicators and syncs field_provenance records.
    """
    fdr = await get_fdr_with_relations(db, fdr_id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {fdr_id} not found",
        )

    pdf_bytes: bytes = b""
    if file:
        if file.filename and not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported for FDR OCR extraction",
            )
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )
        # Store in MinIO if not already uploaded
        file_hash = hashlib.sha256(pdf_bytes).hexdigest()
        object_key = storage_service.upload_fdr_document(
            fdr_id=fdr.id,
            file_bytes=pdf_bytes,
            filename=file.filename or f"fdr_{fdr.id}.pdf",
            content_type=file.content_type or "application/pdf",
        )
        fdr.document_path = object_key
        fdr.document_hash = file_hash
        db.add(fdr)
        await db.flush()
    else:
        # Download from existing MinIO document path
        if not fdr.document_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"FDR #{fdr_id} has no uploaded document. Please upload a PDF file.",
            )
        try:
            pdf_bytes = storage_service.download_fdr_document(fdr.document_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve document from MinIO: {exc}",
            )

    extraction_res, _ = await OCRService.process_fdr_document(
        session=db,
        fdr=fdr,
        pdf_bytes=pdf_bytes,
    )

    return extraction_res


@router.get("/{fdr_id}/discrepancies", response_model=DiscrepancyReportResponse, status_code=status.HTTP_200_OK)
async def get_fdr_discrepancies(
    fdr_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Pass 2: Side-by-Side Discrepancy Validation
    Compares institution-declared form values against OCR-extracted provenance values.
    Flags mismatches (e.g. ₹10,00,000 vs ₹1,00,000) with badge colors:
    - grey: self-declared / unextracted
    - amber: OCR extracted needing review
    - green: verified match
    - red: discrepancy / mismatch
    """
    fdr = await get_fdr_with_relations(db, fdr_id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {fdr_id} not found",
        )

    # Reconstruct extracted fields dictionary from existing Provenance records
    extracted_fields = {}
    for prov in fdr.provenance_records:
        if prov.source_type in (ProvenanceSourceType.OCR_EXTRACTED, ProvenanceSourceType.OFFICER_VERIFIED):
            extracted_fields[prov.field_name] = ExtractedFieldItem(
                field_name=prov.field_name,
                extracted_value=prov.extracted_value,
                confidence_score=prov.confidence_score or 0.0,
                source_snippet=f"Provenance source: {prov.source_type.value}",
                needs_human_review=(prov.confidence_score or 0.0) < 0.85,
            )

    # Parse tamper indicators
    tamper_indicators = []
    if fdr.tamper_indicators:
        try:
            raw_indicators = json.loads(fdr.tamper_indicators)
            tamper_indicators = [TamperIndicatorItem(**ind) for ind in raw_indicators]
        except Exception:
            pass

    # Check duplicates
    dup_check = await OCRService.check_duplicates(
        session=db,
        fdr_id=fdr.id,
        file_hash=fdr.document_hash or "",
        fdr_number=fdr.fdr_number,
        bank_name=fdr.bank_name,
        institution_id=fdr.institution_id,
    )

    return OCRService.compare_discrepancies(
        fdr=fdr,
        extracted_fields=extracted_fields,
        tamper_indicators=tamper_indicators,
        duplicate_check=dup_check,
    )


@router.post("/{fdr_id}/verify-field", response_model=FieldVerificationResponse, status_code=status.HTTP_200_OK)
async def verify_fdr_field(
    fdr_id: int,
    payload: FieldVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Scrutiny Officer Field Verification:
    Allows an officer to accept or correct an extracted field.
    Upgrades field provenance to OFFICER_VERIFIED and commits a chained SHA-256 audit entry.
    """
    fdr = await get_fdr_with_relations(db, fdr_id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {fdr_id} not found",
        )

    prov, audit_entry = await OCRService.verify_field(
        session=db,
        fdr=fdr,
        field_name=payload.field_name,
        accepted_value=payload.accepted_value,
        officer_id=payload.officer_id,
        remarks=payload.remarks,
    )

    return FieldVerificationResponse(
        message=f"Field '{payload.field_name}' successfully verified by officer {payload.officer_id}.",
        fdr_id=fdr.id,
        field_name=payload.field_name,
        verified_value=payload.accepted_value,
        provenance_source=prov.source_type.value,
        audit_hash=audit_entry.current_hash,
    )
