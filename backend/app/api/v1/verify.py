from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.fdr import FDR, FDRStatus
from app.schemas.verify import ClearanceCompletionSummary, PublicVerificationResponse
from app.services.noc_service import NOC_BUCKET, NOCService, get_public_key_hex
from app.services.storage_service import storage_service

router = APIRouter()


@router.get("/{fdr_id}", response_model=PublicVerificationResponse, status_code=status.HTTP_200_OK)
async def verify_fdr_release_status(
    fdr_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Public verification endpoint (QR code destination):
    Validates the authenticity of an FDR release order live by re-computing and
    checking the Ed25519 digital signature against the release payload.
    Returns instrument details, clearance completion timestamps, and NOC download URL.
    """
    stmt = (
        select(FDR)
        .where(FDR.id == fdr_id)
        .options(
            selectinload(FDR.clearances),
            selectinload(FDR.institution),
        )
    )
    result = await db.execute(stmt)
    fdr = result.scalar_one_or_none()
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR record with ID {fdr_id} does not exist in AICTE FinTrust registry.",
        )

    is_released = fdr.status == FDRStatus.RELEASED
    is_signature_valid = False

    if fdr.noc_signature:
        is_signature_valid = NOCService.verify_noc_signature(fdr)

    noc_download_url: Optional[str] = None
    if fdr.noc_path:
        try:
            noc_download_url = storage_service.generate_presigned_url(
                object_key=fdr.noc_path,
                expires_in_seconds=300,
                bucket_name=NOC_BUCKET,
            )
        except Exception:
            noc_download_url = None

    clearance_summaries = [
        ClearanceCompletionSummary(
            cell_name=c.cell_name.value,
            status=c.status.value,
            officer_id=c.officer_id,
            completed_at=c.updated_at.isoformat() if c.updated_at else None,
            remarks=c.remarks,
        )
        for c in (fdr.clearances or [])
    ]

    inst_name = fdr.institution.name if fdr.institution else f"Institution {fdr.institution_id}"
    aicte_id = fdr.institution.aicte_permanent_id if fdr.institution else f"AICTE-{fdr.institution_id}"

    if is_released and is_signature_valid:
        msg = "Official AICTE Discharge Order (NOC) verified. Digital signature (Ed25519) is cryptographically valid."
    elif is_released and not is_signature_valid:
        msg = "TAMPER WARNING: The digital signature verification failed. Release record may have been altered!"
    else:
        msg = f"Instrument is currently in '{fdr.status.value}' status. Release has not been authorized."

    return PublicVerificationResponse(
        fdr_id=fdr.id,
        fdr_number=fdr.fdr_number or "UNSPECIFIED",
        institution_name=inst_name,
        aicte_permanent_id=aicte_id,
        bank_name=fdr.bank_name or "UNSPECIFIED",
        principal_amount=str(fdr.principal_amount or "0.00"),
        fdr_status=fdr.status,
        is_released=is_released,
        is_signature_valid=is_signature_valid,
        signature_algorithm="Ed25519 (RFC 8032)",
        ed25519_signature=fdr.noc_signature,
        public_key_hex=get_public_key_hex() if fdr.noc_signature else None,
        noc_document_path=fdr.noc_path,
        noc_download_url=noc_download_url,
        clearances=clearance_summaries,
        verification_timestamp=datetime.now(timezone.utc).isoformat(),
        message=msg,
    )
