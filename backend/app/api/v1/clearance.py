from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
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
    ReleaseRequestResponse,
)
from app.services.audit_service import AuditService
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
