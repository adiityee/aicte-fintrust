from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.models.provenance import Provenance, ProvenanceSourceType
from app.schemas.fdr import FDRDraftRequest, FDRResponse, FDRSubmitResponse
from app.services.audit_service import AuditService
from app.services.state_machine import InvalidStateTransitionError, StateMachineService

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
