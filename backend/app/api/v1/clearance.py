from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.clearance import Clearance, ClearanceCell, ClearanceStatus
from app.models.fdr import FDR, FDRStatus
from app.schemas.clearance import (
    ClearanceActionRequest,
    ClearanceActionResponse,
    ClearanceResponse,
    ReleaseApprovalResponse,
    ReleaseRequestResponse,
)
from app.services.audit_service import AuditService
from app.services.noc_service import NOCService
from app.services.state_machine import InvalidStateTransitionError, StateMachineService

router = APIRouter()

CONFIGURED_RELEASE_CELLS: List[ClearanceCell] = [
    ClearanceCell.PGRC,
    ClearanceCell.VIGILANCE,
    ClearanceCell.APPROVAL_BUREAU,
    ClearanceCell.LEGAL,
    ClearanceCell.FINANCE,
]


@router.post("/{fdr_id}/request-release", response_model=ReleaseRequestResponse)
async def request_fdr_release(
    fdr_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate FDR Release Gate:
    1. Validates FDR existence and transitions status to RELEASE_REQUESTED.
    2. Spawns parallel clearance tasks across 5 configured cells:
       PGRC, VIGILANCE, APPROVAL_BUREAU, LEGAL, and FINANCE.
    3. Records an immutable SHA-256 audit entry.
    """
    fdr = await db.get(FDR, fdr_id)
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {fdr_id} not found",
        )

    # Transition state to RELEASE_REQUESTED if not already in that status
    if fdr.status != FDRStatus.RELEASE_REQUESTED:
        try:
            await StateMachineService.transition(
                session=db,
                fdr=fdr,
                target_state=FDRStatus.RELEASE_REQUESTED,
                user_id=f"INSTITUTION_{fdr.institution_id}",
                reason="Release request initiated by institution",
            )
        except InvalidStateTransitionError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            )

    # Explicitly fetch existing clearance records
    c_stmt = select(Clearance).where(Clearance.fdr_id == fdr.id)
    c_res = await db.execute(c_stmt)
    existing_cells = {c.cell_name: c for c in c_res.scalars().all()}

    tasks_to_return: List[Clearance] = []

    for cell in CONFIGURED_RELEASE_CELLS:
        if cell in existing_cells:
            task = existing_cells[cell]
            task.status = ClearanceStatus.PENDING
            task.remarks = None
            task.officer_id = None
            db.add(task)
            tasks_to_return.append(task)
        else:
            task = Clearance(
                fdr_id=fdr.id,
                cell_name=cell,
                status=ClearanceStatus.PENDING,
            )
            db.add(task)
            tasks_to_return.append(task)

    await db.flush()

    await AuditService.record_event(
        session=db,
        action="RELEASE_REQUESTED_CLEARANCES_INITIALIZED",
        payload={
            "fdr_id": fdr.id,
            "cells": [c.value for c in CONFIGURED_RELEASE_CELLS],
        },
        user_id=f"INSTITUTION_{fdr.institution_id}",
        details=f"Parallel clearance tasks initialized for FDR {fdr.id}",
    )

    return ReleaseRequestResponse(
        message="Release request registered. Parallel clearance tasks spawned for all 5 cells.",
        fdr_id=fdr.id,
        fdr_status=fdr.status,
        clearances=[ClearanceResponse.model_validate(t) for t in tasks_to_return],
    )


@router.put("/{task_id}/action", response_model=ClearanceActionResponse)
async def update_clearance_action(
    task_id: int,
    payload: ClearanceActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an officer's clearance action (APPROVED or REJECTED with remarks).
    Automatically checks if all parallel cells have approved:
    once all 5 cells approve, automatically unlocks and transitions FDR to CLEARANCES_APPROVED.
    """
    task = await db.get(Clearance, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clearance task with ID {task_id} not found",
        )

    task.status = payload.status
    task.remarks = payload.remarks
    task.officer_id = payload.officer_id
    db.add(task)
    await db.flush()

    fdr = await db.get(FDR, task.fdr_id)
    officer_str = payload.officer_id or "OFFICER"

    # Log individual clearance action in audit ledger
    await AuditService.record_event(
        session=db,
        action="CLEARANCE_CELL_ACTION",
        payload={
            "task_id": task.id,
            "fdr_id": fdr.id,
            "cell": task.cell_name.value,
            "status": task.status.value,
            "officer_id": task.officer_id,
            "remarks": task.remarks,
        },
        user_id=officer_str,
        details=f"Cell {task.cell_name.value} marked {task.status.value} for FDR {fdr.id}",
    )

    # Load FDR with its clearances eagerly
    fdr_stmt = (
        select(FDR)
        .where(FDR.id == task.fdr_id)
        .options(selectinload(FDR.clearances))
    )
    fdr_res = await db.execute(fdr_stmt)
    fdr = fdr_res.scalar_one()

    all_approved = False
    clearance_status_map = {c.cell_name: c.status for c in fdr.clearances}
    all_cells_approved = all(
        clearance_status_map.get(cell) == ClearanceStatus.APPROVED
        for cell in CONFIGURED_RELEASE_CELLS
    ) and len(fdr.clearances) >= len(CONFIGURED_RELEASE_CELLS)

    if all_cells_approved and fdr.status == FDRStatus.RELEASE_REQUESTED:
        # Transition FDR to CLEARANCES_APPROVED
        await StateMachineService.transition(
            session=db,
            fdr=fdr,
            target_state=FDRStatus.CLEARANCES_APPROVED,
            user_id=officer_str,
            reason="All 5 clearance cells (PGRC, VIGILANCE, APPROVAL_BUREAU, LEGAL, FINANCE) approved",
        )
        all_approved = True

    return ClearanceActionResponse(
        message=f"Clearance task for cell '{task.cell_name.value}' updated to '{task.status.value}'.",
        task=ClearanceResponse.model_validate(task),
        fdr_status=fdr.status,
        all_cells_approved=(fdr.status == FDRStatus.CLEARANCES_APPROVED),
    )


@router.post("/{fdr_id}/approve-release", response_model=ReleaseApprovalResponse, status_code=status.HTTP_200_OK)
async def approve_fdr_release(
    fdr_id: int,
    officer_id: str = Query("COMPETENT_AUTHORITY", description="Officer ID authorizing the discharge"),
    remarks: Optional[str] = Query(None, description="Optional release remarks"),
    db: AsyncSession = Depends(get_db),
):
    """
    Competent Authority Final Release Authorization:
    1. Validates that parallel clearances have all APPROVED.
    2. Invokes noc_service to sign the release payload with Ed25519 DSC.
    3. Generates the official AICTE Discharge Order (NOC) PDF with embedded QR verification code.
    4. Uploads NOC into MinIO under 'noc-certificates'.
    5. Transitions FDR status to RELEASED.
    6. Appends an immutable SHA-256 block into the audit chain.
    """
    fdr_stmt = (
        select(FDR)
        .where(FDR.id == fdr_id)
        .options(
            selectinload(FDR.clearances),
            selectinload(FDR.institution),
        )
    )
    res = await db.execute(fdr_stmt)
    fdr = res.scalar_one_or_none()
    if not fdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FDR with ID {fdr_id} not found",
        )

    # Clearance gate validation: check that all 5 cells are approved
    clearance_status_map = {c.cell_name: c.status for c in fdr.clearances}
    all_cells_approved = all(
        clearance_status_map.get(cell) == ClearanceStatus.APPROVED
        for cell in CONFIGURED_RELEASE_CELLS
    ) and len(fdr.clearances) >= len(CONFIGURED_RELEASE_CELLS)

    if not all_cells_approved:
        unapproved = [
            c.value for c in CONFIGURED_RELEASE_CELLS
            if clearance_status_map.get(c) != ClearanceStatus.APPROVED
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Release gate locked: Pending or unapproved cell(s): {', '.join(unapproved)}. Final release authorization is blocked.",
        )

    # Ensure status is CLEARANCES_APPROVED before transition to RELEASED
    if fdr.status != FDRStatus.CLEARANCES_APPROVED:
        fdr.status = FDRStatus.CLEARANCES_APPROVED
        db.add(fdr)
        await db.flush()

    # Generate and sign the digital NOC with Ed25519 DSC and embedded QR
    noc_info = await NOCService.generate_and_sign_noc(
        session=db,
        fdr=fdr,
        officer_id=officer_id,
    )

    # Transition FDR status to RELEASED via StateMachine
    await StateMachineService.transition(
        session=db,
        fdr=fdr,
        target_state=FDRStatus.RELEASED,
        user_id=officer_id,
        reason=f"Release authorized by {officer_id}. Digital NOC issued: {noc_info['noc_path']}",
    )

    # Record cryptographic audit entry
    await AuditService.record_event(
        session=db,
        action="RELEASE_AUTHORIZED_NOC_ISSUED",
        payload={
            "fdr_id": fdr.id,
            "fdr_number": fdr.fdr_number,
            "institution_id": fdr.institution_id,
            "bank_name": fdr.bank_name,
            "principal_amount": str(fdr.principal_amount),
            "noc_path": noc_info["noc_path"],
            "ed25519_signature": noc_info["noc_signature"],
            "public_key": noc_info["public_key_hex"],
            "authorizing_officer": officer_id,
            "remarks": remarks,
        },
        user_id=officer_id,
        details=f"Competent Authority authorized release of FDR {fdr.fdr_number}. NOC generated.",
    )

    return ReleaseApprovalResponse(
        message="FDR release authorized successfully. Official Digital NOC generated and signed.",
        fdr_id=fdr.id,
        fdr_status=fdr.status,
        noc_document_path=noc_info["noc_path"],
        noc_download_url=noc_info["presigned_url"],
        ed25519_signature=noc_info["noc_signature"],
        public_verification_url=noc_info["public_verification_url"],
        authorized_by=officer_id,
        authorized_at=datetime.now(timezone.utc).isoformat(),
    )
