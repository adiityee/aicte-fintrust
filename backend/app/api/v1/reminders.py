from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.reminder import ReminderAlert, ReminderStatus, ReminderType
from app.schemas.reminder import (
    CheckMaturityResponse,
    EncashmentNoticeResponse,
    ReminderAcknowledgeRequest,
    ReminderAlertResponse,
)
from app.services.audit_service import AuditService
from app.services.reminder_service import ReminderService

router = APIRouter()


@router.get("/active", response_model=List[ReminderAlertResponse], status_code=status.HTTP_200_OK)
async def get_active_reminders(
    role: str = Query("ALL", description="Filter by role: INSTITUTION, REGIONAL_OFFICER, ALL"),
    institution_id: Optional[int] = Query(None, description="Optional institution ID filter"),
    officer_id: Optional[str] = Query(None, description="Optional officer ID filter"),
    status_filter: Optional[ReminderStatus] = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns active (pending, sent, or escalated) reminder alerts.
    Filters by caller's role (Institutions see their own alerts; Regional Officers see escalated alerts).
    """
    query = select(ReminderAlert)

    if status_filter:
        query = query.where(ReminderAlert.status == status_filter)
    else:
        query = query.where(
            ReminderAlert.status.in_([
                ReminderStatus.PENDING,
                ReminderStatus.SENT,
                ReminderStatus.ESCALATED,
            ])
        )

    role_upper = role.upper()
    if role_upper == "REGIONAL_OFFICER":
        query = query.where(ReminderAlert.status == ReminderStatus.ESCALATED)
        if officer_id:
            query = query.where(
                (ReminderAlert.assigned_officer_id == officer_id) | (ReminderAlert.assigned_officer_id == "REGIONAL_OFFICER")
            )
    elif role_upper == "INSTITUTION" and institution_id is not None:
        query = query.where(ReminderAlert.institution_id == institution_id)
    elif institution_id is not None:
        query = query.where(ReminderAlert.institution_id == institution_id)

    query = query.order_by(ReminderAlert.due_date.asc(), ReminderAlert.id.desc())
    result = await db.execute(query)
    alerts = list(result.scalars().all())

    return [ReminderAlertResponse.model_validate(a) for a in alerts]


@router.post("/{id}/acknowledge", response_model=ReminderAlertResponse, status_code=status.HTTP_200_OK)
async def acknowledge_reminder(
    id: int,
    payload: ReminderAcknowledgeRequest = ReminderAcknowledgeRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Marks an active reminder alert as ACKNOWLEDGED by the institution or officer,
    stopping automated supervisor escalation.
    """
    alert = await db.get(ReminderAlert, id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder alert with ID {id} not found",
        )

    if alert.status == ReminderStatus.ACKNOWLEDGED:
        return ReminderAlertResponse.model_validate(alert)

    actor_str = payload.actor_id or f"INSTITUTION_{alert.institution_id}"
    now_utc = datetime.now(timezone.utc)
    alert.status = ReminderStatus.ACKNOWLEDGED
    alert.acknowledged_at = now_utc
    alert.acknowledged_by = actor_str
    alert.updated_at = now_utc
    db.add(alert)
    await db.flush()

    await AuditService.record_event(
        session=db,
        action="REMINDER_ALERT_ACKNOWLEDGED",
        payload={
            "alert_id": alert.id,
            "fdr_id": alert.fdr_id,
            "acknowledged_by": actor_str,
            "offset": alert.days_offset,
        },
        user_id=actor_str,
        details=f"Alert {alert.id} acknowledged by {actor_str}",
    )

    return ReminderAlertResponse.model_validate(alert)


@router.post("/check-maturities", response_model=CheckMaturityResponse, status_code=status.HTTP_200_OK)
async def trigger_maturity_checks(
    target_date: Optional[date] = Query(None, description="Optional reference date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers the proactive maturity calculation engine:
    1. Generates alerts at 90, 60, 30, 15, 7, 1 day intervals (idempotently).
    2. Escalates unacknowledged alerts <= 7 days before deadline to Regional Officer.
    """
    new_alerts = await ReminderService.check_upcoming_maturities(db, reference_date=target_date)
    escalated = await ReminderService.check_and_escalate_unacknowledged(db, reference_date=target_date)

    combined_alerts = list({a.id: a for a in (new_alerts + escalated)}.values())

    return CheckMaturityResponse(
        checked_at=datetime.now(timezone.utc).isoformat(),
        new_alerts_created=len(new_alerts),
        escalated_alerts_count=len(escalated),
        alerts=[ReminderAlertResponse.model_validate(a) for a in combined_alerts],
    )


@router.post("/encashment-notice/{fdr_id}", response_model=EncashmentNoticeResponse, status_code=status.HTTP_200_OK)
async def create_encashment_notice(
    fdr_id: int,
    officer_id: Optional[str] = Query("REGIONAL_OFFICER_01", description="Assigned officer ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers safe default-encashment drafting for an overdue/matured FDR.
    Drafts an official demand notice PDF into an officer's approval queue.
    """
    try:
        result = await ReminderService.draft_encashment_notice(
            session=db,
            fdr_id=fdr_id,
            officer_id=officer_id,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Encashment notice drafting failed: {exc}",
        )

    return EncashmentNoticeResponse(
        message=result["message"],
        fdr_id=result["fdr_id"],
        fdr_status=result["fdr_status"],
        notice_reference=result["notice_reference"],
        notice_pdf_path=result["notice_pdf_path"],
        officer_queue=result["officer_queue"],
    )
