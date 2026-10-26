from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.models.provenance import Provenance, ProvenanceSourceType
from app.schemas.fdr import (
    FDRDocumentUrlResponse,
    FDRDraftRequest,
    FDRResponse,
    FDRSubmitResponse,
    FDRUploadDocumentResponse,
)
from app.schemas.ocr import DiscrepancyReportResponse
from app.schemas.provenance import FDRProvenanceResponse, ProvenanceResponse
from app.services.audit_service import AuditService
from app.services.ocr_forensics import OCRForensicService
from app.services.state_machine import InvalidStateTransitionError, StateMachineService
from app.services.storage_service import storage_service

router = APIRouter()


async def get_fdr_with_relations(session: AsyncSession, fdr_id: int) -> Optional[FDR]:
    """Helper to query FDR along with related provenance and clearance items."""
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


@router.post("/draft", response_model=FDRResponse, status_code=status.HTTP_200_OK)
async def create_or_update_draft(
    payload: FDRDraftRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update a draft FDR record.
    Supports partial saves before final submission.
    """
    # Verify institution existence or auto-provision for test/demo ease
    inst = await db.get(Institution, payload.institution_id)
    if not inst:
        inst = Institution(
            id=payload.institution_id,
            aicte_permanent_id=f"AICTE-{payload.institution_id}",
            name=f"AICTE Approved Institution {payload.institution_id}",
            state="Delhi",
            email=f"registrar{payload.institution_id}@aicte.gov.in",
        )
        db.add(inst)
        await db.flush()

    existing_prov_map = {}

    if payload.id:
        fdr = await get_fdr_with_relations(db, payload.id)
        if not fdr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FDR draft with ID {payload.id} not found",
            )
        if fdr.status not in (FDRStatus.DRAFT, FDRStatus.QUERY_RAISED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit FDR in status '{fdr.status.value}'. Only DRAFT or QUERY_RAISED FDRs can be updated.",
            )
        # Fetch existing provenance records explicitly
        prov_stmt = select(Provenance).where(Provenance.fdr_id == fdr.id)
        prov_res = await db.execute(prov_stmt)
        existing_prov_map = {p.field_name: p for p in prov_res.scalars().all()}
    else:
        fdr = FDR(
            institution_id=payload.institution_id,
            status=FDRStatus.DRAFT,
            lien_holder=payload.lien_holder or "AICTE",
        )
        db.add(fdr)
        await db.flush()

    # Update attributes if provided
    tracked_fields = [
        ("fdr_number", payload.fdr_number),
        ("bank_name", payload.bank_name),
        ("ifsc_code", payload.ifsc_code),
        ("principal_amount", payload.principal_amount),
        ("interest_rate", payload.interest_rate),
        ("issue_date", payload.issue_date),
        ("maturity_date", payload.maturity_date),
        ("lien_holder", payload.lien_holder),
        ("document_path", payload.document_path),
    ]

    for field_name, val in tracked_fields:
        if val is not None:
            setattr(fdr, field_name, val)

            # Auto-tag field provenance as INSTITUTION_ENTERED
            if field_name in existing_prov_map:
                prov = existing_prov_map[field_name]
                prov.extracted_value = str(val)
                prov.source_type = ProvenanceSourceType.INSTITUTION_ENTERED
                prov.confidence_score = 1.0
                db.add(prov)
            else:
                new_prov = Provenance(
                    fdr_id=fdr.id,
                    field_name=field_name,
                    source_type=ProvenanceSourceType.INSTITUTION_ENTERED,
                    confidence_score=1.0,
                    extracted_value=str(val),
                )
                db.add(new_prov)
                existing_prov_map[field_name] = new_prov

    await db.flush()

    # Audit draft update
    await AuditService.record_event(
        session=db,
        action="FDR_DRAFT_SAVED",
        payload={"fdr_id": fdr.id, "institution_id": fdr.institution_id, "status": fdr.status.value},
        user_id=f"INSTITUTION_{fdr.institution_id}",
        details=f"Draft FDR {fdr.id} saved",
    )

    refreshed_fdr = await get_fdr_with_relations(db, fdr.id)
    return FDRResponse.model_validate(refreshed_fdr)


@router.post("/{id}/submit", response_model=FDRSubmitResponse, status_code=status.HTTP_200_OK)
async def submit_fdr(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a draft FDR into the official scrutiny pipeline.
    Validates mandatory requirements, transitions state to SUBMITTED,
    and logs an immutable SHA-256 chained audit record.
    """
    fdr = await get_fdr_with_relations(db, id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {id} not found",
        )

    try:
        await StateMachineService.transition(
            session=db,
            fdr=fdr,
            target_state=FDRStatus.SUBMITTED,
            user_id=f"INSTITUTION_{fdr.institution_id}",
            reason="FDR officially submitted for AICTE scrutiny",
        )
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    # Compute additional cryptographic audit payload entry
    audit_entry = await AuditService.record_event(
        session=db,
        action="FDR_SUBMITTED",
        payload={
            "fdr_id": fdr.id,
            "fdr_number": fdr.fdr_number,
            "bank_name": fdr.bank_name,
            "principal_amount": str(fdr.principal_amount),
            "ifsc_code": fdr.ifsc_code,
            "issue_date": str(fdr.issue_date),
            "maturity_date": str(fdr.maturity_date),
        },
        user_id=f"INSTITUTION_{fdr.institution_id}",
        details=f"FDR {fdr.fdr_number} submitted for scrutiny",
    )

    refreshed_fdr = await get_fdr_with_relations(db, fdr.id)
    return FDRSubmitResponse(
        message="FDR submitted successfully and locked for scrutiny.",
        fdr=FDRResponse.model_validate(refreshed_fdr),
        audit_hash=audit_entry.current_hash,
    )


@router.get("/{id}", response_model=FDRResponse)
async def get_fdr(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch comprehensive FDR details, including its field-level provenance badges,
    clearance tasks, and current lifecycle state.
    """
    fdr = await get_fdr_with_relations(db, id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {id} not found",
        )
    return FDRResponse.model_validate(fdr)


@router.get("/institution/{inst_id}", response_model=List[FDRResponse])
async def get_institution_fdrs(
    inst_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all FDR records deposited by an institution.
    """
    stmt = (
        select(FDR)
        .where(FDR.institution_id == inst_id)
        .options(
            selectinload(FDR.provenance_records),
            selectinload(FDR.clearances),
            selectinload(FDR.institution),
        )
        .order_by(FDR.id.desc())
    )
    result = await db.execute(stmt)
    records = list(result.scalars().all())
    return [FDRResponse.model_validate(r) for r in records]


@router.post("/{id}/upload-document", response_model=FDRUploadDocumentResponse, status_code=status.HTTP_200_OK)
async def upload_fdr_document(
    id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts multipart/form-data (PDF), uploads to storage with server-side AES-256 encryption,
    computes SHA-256 file hash, links document reference to FDR, logs an immutable audit entry,
    and invokes OCRForensicService to extract key fields, inspect forensics, and auto-populate blanks.
    """
    fdr = await db.get(FDR, id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {id} not found",
        )

    if file.filename and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents (.pdf) are accepted for FDR uploads",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Compute SHA-256 hash of document bytes
    file_hash = hashlib.sha256(contents).hexdigest()

    # Upload to storage with AES-256 Server-Side Encryption (SSE-S3)
    try:
        object_key = storage_service.upload_fdr_document(
            fdr_id=fdr.id,
            file_bytes=contents,
            filename=file.filename or f"fdr_{fdr.id}.pdf",
            content_type=file.content_type or "application/pdf",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage operation failed: {exc}",
        )

    # Link document reference and hash to FDR
    fdr.document_path = object_key
    fdr.document_hash = file_hash
    db.add(fdr)

    # Record provenance for document file
    prov_stmt = select(Provenance).where(
        Provenance.fdr_id == fdr.id,
        Provenance.field_name == "document_file",
    )
    prov_res = await db.execute(prov_stmt)
    prov = prov_res.scalar_one_or_none()
    if prov:
        prov.extracted_value = file_hash
        prov.source_type = ProvenanceSourceType.INSTITUTION_ENTERED
        prov.confidence_score = 1.0
        db.add(prov)
    else:
        new_prov = Provenance(
            fdr_id=fdr.id,
            field_name="document_file",
            source_type=ProvenanceSourceType.INSTITUTION_ENTERED,
            confidence_score=1.0,
            extracted_value=file_hash,
        )
        db.add(new_prov)

    # Invoke OCRForensicService for text extraction and forensics
    extracted_summary: Dict[str, Optional[str]] = {}
    tamper_count = 0

    try:
        # a) Perform PDF forensic checks
        tamper_indicators = OCRForensicService.detect_tamper_indicators(
            pdf_bytes=contents,
            issue_date=fdr.issue_date,
        )
        tamper_count = len(tamper_indicators)
        fdr.tamper_indicators = json.dumps([t.model_dump() for t in tamper_indicators]) if tamper_indicators else None

        # b) Extract key fields (FDR Number, Bank Name, Principal Amount, Maturity Date, etc.)
        extracted_fields, _, _ = OCRForensicService.extract_from_pdf(contents)

        # c) Save extracted values into FieldProvenance records with source_type='OCR_EXTRACTED'
        await OCRForensicService.sync_provenance_records(
            session=db,
            fdr_id=fdr.id,
            extracted_fields=extracted_fields,
        )

        # d) Auto-populate draft FDR fields if they are currently blank
        if fdr.status in (FDRStatus.DRAFT, FDRStatus.QUERY_RAISED):
            if not fdr.fdr_number and extracted_fields.get("fdr_number") and extracted_fields["fdr_number"].extracted_value:
                fdr.fdr_number = extracted_fields["fdr_number"].extracted_value
            if not fdr.bank_name and extracted_fields.get("bank_name") and extracted_fields["bank_name"].extracted_value:
                fdr.bank_name = extracted_fields["bank_name"].extracted_value
            if not fdr.ifsc_code and extracted_fields.get("ifsc_code") and extracted_fields["ifsc_code"].extracted_value:
                fdr.ifsc_code = extracted_fields["ifsc_code"].extracted_value
            if fdr.principal_amount is None and extracted_fields.get("principal_amount") and extracted_fields["principal_amount"].extracted_value:
                parsed_amt = OCRForensicService.parse_amount(extracted_fields["principal_amount"].extracted_value)
                if parsed_amt is not None:
                    fdr.principal_amount = parsed_amt
            if fdr.interest_rate is None and extracted_fields.get("interest_rate") and extracted_fields["interest_rate"].extracted_value:
                try:
                    fdr.interest_rate = Decimal(extracted_fields["interest_rate"].extracted_value)
                except Exception:
                    pass
            if fdr.issue_date is None and extracted_fields.get("issue_date") and extracted_fields["issue_date"].extracted_value:
                parsed_d = OCRForensicService.parse_date(extracted_fields["issue_date"].extracted_value)
                if parsed_d is not None:
                    fdr.issue_date = parsed_d
            if fdr.maturity_date is None and extracted_fields.get("maturity_date") and extracted_fields["maturity_date"].extracted_value:
                parsed_d = OCRForensicService.parse_date(extracted_fields["maturity_date"].extracted_value)
                if parsed_d is not None:
                    fdr.maturity_date = parsed_d
            if not fdr.lien_holder and extracted_fields.get("lien_holder") and extracted_fields["lien_holder"].extracted_value:
                fdr.lien_holder = extracted_fields["lien_holder"].extracted_value

        needs_review = any(f.needs_human_review for f in extracted_fields.values()) or bool(tamper_indicators)
        fdr.ocr_status = "NEEDS_HUMAN_REVIEW" if needs_review else "PROCESSED"

        extracted_summary = {
            k: v.extracted_value for k, v in extracted_fields.items() if v.extracted_value is not None
        }

        db.add(fdr)
    except Exception as ocr_exc:
        # Non-fatal to file upload, but logged
        print(f"[FinTrust Warning] OCR forensic processing encountered an issue: {ocr_exc}")

    await db.flush()

    # Write immutable audit entry
    await AuditService.record_event(
        session=db,
        action="FDR_DOCUMENT_UPLOADED",
        payload={
            "fdr_id": fdr.id,
            "filename": file.filename,
            "file_size": len(contents),
            "file_hash": file_hash,
            "object_key": object_key,
            "ocr_status": fdr.ocr_status,
        },
        user_id=f"INSTITUTION_{fdr.institution_id}",
        details=f"Uploaded FDR PDF document {file.filename} (SHA-256: {file_hash}, OCR: {fdr.ocr_status})",
    )

    return FDRUploadDocumentResponse(
        message="Document uploaded and processed via OCR successfully.",
        fdr_id=fdr.id,
        document_path=object_key,
        document_hash=file_hash,
        file_size_bytes=len(contents),
        extracted_fields=extracted_summary,
        ocr_status=fdr.ocr_status,
        tamper_indicators_count=tamper_count,
    )


@router.get("/{id}/provenance", response_model=FDRProvenanceResponse, status_code=status.HTTP_200_OK)
async def get_fdr_provenance(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Return all field provenance records and confidence flags for the split-screen comparison UI.
    Provides verifiable source badges:
    - grey: INSTITUTION_ENTERED (self-declared)
    - amber: OCR_EXTRACTED (AI extracted with valid confidence)
    - red: OCR_EXTRACTED with low confidence (< 0.85) or discrepancy
    - green: OFFICER_VERIFIED / BANK_CONFIRMED
    """
    fdr = await db.get(FDR, id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {id} not found",
        )

    stmt = select(Provenance).where(Provenance.fdr_id == id).order_by(Provenance.id.asc())
    res = await db.execute(stmt)
    records = list(res.scalars().all())

    confidence_flags = {}
    needs_human_review = False

    for p in records:
        score = p.confidence_score or 0.0
        is_flagged = score < 0.85
        if is_flagged and p.source_type == ProvenanceSourceType.OCR_EXTRACTED:
            needs_human_review = True

        badge_color = "grey"
        if p.source_type in (ProvenanceSourceType.BANK_CONFIRMED, ProvenanceSourceType.OFFICER_VERIFIED):
            badge_color = "green"
        elif p.source_type == ProvenanceSourceType.OCR_EXTRACTED:
            badge_color = "red" if is_flagged else "amber"

        confidence_flags[p.field_name] = {
            "confidence_score": score,
            "source_type": p.source_type.value,
            "flagged": is_flagged,
            "badge_color": badge_color,
            "extracted_value": p.extracted_value,
        }

    return FDRProvenanceResponse(
        fdr_id=fdr.id,
        provenance_records=[ProvenanceResponse.model_validate(p) for p in records],
        confidence_flags=confidence_flags,
        needs_human_review=needs_human_review,
    )


@router.get("/{id}/document-url", response_model=FDRDocumentUrlResponse)
async def get_fdr_document_url(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a secure, temporary pre-signed download URL valid for under 5 minutes (300s).
    """
    fdr = await db.get(FDR, id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {id} not found",
        )

    if not fdr.document_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document has been uploaded for FDR {id}",
        )

    try:
        presigned_url = storage_service.generate_presigned_url(
            object_key=fdr.document_path,
            expires_in_seconds=300,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned download URL: {exc}",
        )

    return FDRDocumentUrlResponse(
        fdr_id=fdr.id,
        document_path=fdr.document_path,
        presigned_url=presigned_url,
        expires_in_seconds=300,
    )


@router.post("/{id}/validate-ocr", response_model=DiscrepancyReportResponse, status_code=status.HTTP_200_OK)
async def validate_fdr_ocr(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Executes Dual-Pass Verification (Extraction, Forensics & Side-by-Side Discrepancy Matching)
    for the FDR's uploaded document and returns discrepancy analysis.
    """
    fdr = await get_fdr_with_relations(db, id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {id} not found",
        )

    if not fdr.document_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No document uploaded for FDR {id} yet. Please upload a PDF first.",
        )

    try:
        pdf_bytes = storage_service.download_fdr_document(fdr.document_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document from storage: {exc}",
        )

    _, discrepancy_report = await OCRForensicService.process_fdr_document(
        session=db,
        fdr=fdr,
        pdf_bytes=pdf_bytes,
    )

    return discrepancy_report
