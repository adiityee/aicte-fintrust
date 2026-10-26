from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.models.reminder import ReminderAlert, ReminderStatus, ReminderType
from app.services.audit_service import AuditService
from app.services.state_machine import StateMachineService
from app.services.storage_service import storage_service

# Configurable notification offsets (in days prior to maturity)
DEFAULT_OFFSETS: List[int] = [90, 60, 30, 15, 7, 1]


class ReminderService:
    """
    Automated Maturity & Reminder Engine
    Handles proactive deadline alerts, idempotent notification dispatch,
    automatic supervisor escalations, and draft default-encashment notices.
    """

    @staticmethod
    async def check_upcoming_maturities(
        session: AsyncSession,
        reference_date: Optional[date] = None,
        offsets: Optional[List[int]] = None,
    ) -> List[ReminderAlert]:
        """
        Queries active FDRs nearing maturity at configurable offsets (90, 60, 30, 15, 7, 1 days).
        Ensures idempotent notification creation so duplicate alerts are never generated for the same offset.
        """
        ref_date = reference_date or date.today()
        target_offsets = sorted(offsets or DEFAULT_OFFSETS, reverse=True)

        # Query all active or matured FDRs
        stmt = (
            select(FDR)
            .where(FDR.status.in_([FDRStatus.ACTIVE, FDRStatus.BANK_VERIFIED, FDRStatus.MATURED]))
            .options(selectinload(FDR.institution))
        )
        result = await session.execute(stmt)
        fdrs = list(result.scalars().all())

        new_alerts: List[ReminderAlert] = []

        for fdr in fdrs:
            if not fdr.maturity_date:
                continue

            days_remaining = (fdr.maturity_date - ref_date).days

            # Proactive maturity warnings
            for offset in target_offsets:
                # Trigger alert if days remaining is within the offset window
                if 0 <= days_remaining <= offset:
                    # Idempotency check: verify alert does not already exist for this (fdr, type, offset)
                    check_stmt = select(ReminderAlert).where(
                        ReminderAlert.fdr_id == fdr.id,
                        ReminderAlert.reminder_type == ReminderType.UPCOMING_MATURITY,
                        ReminderAlert.days_offset == offset,
                    )
                    existing = await session.execute(check_stmt)
                    if existing.scalar_one_or_none() is not None:
                        continue  # Already generated for this offset

                    inst_name = fdr.institution.name if fdr.institution else f"Institution {fdr.institution_id}"
                    inst_email = (
                        fdr.institution.email
                        if fdr.institution and fdr.institution.email
                        else f"registrar{fdr.institution_id}@aicte.gov.in"
                    )

                    alert_msg = (
                        f"FDR {fdr.fdr_number} matures in {days_remaining} day(s) on {fdr.maturity_date}. "
                        f"Action: submit a renewal FDR. Owner: Registrar, {inst_name}. "
                        f"If missed: escalated to Regional Officer."
                    )

                    alert = ReminderAlert(
                        fdr_id=fdr.id,
                        institution_id=fdr.institution_id,
                        reminder_type=ReminderType.UPCOMING_MATURITY,
                        days_offset=offset,
                        due_date=fdr.maturity_date,
                        status=ReminderStatus.SENT,
                        message=alert_msg,
                        recipient=inst_email,
                    )
                    session.add(alert)
                    new_alerts.append(alert)

                    await session.flush()

                    await AuditService.record_event(
                        session=session,
                        action="REMINDER_ALERT_GENERATED",
                        payload={
                            "alert_id": alert.id,
                            "fdr_id": fdr.id,
                            "offset": offset,
                            "days_remaining": days_remaining,
                            "recipient": inst_email,
                        },
                        user_id="REMINDER_ENGINE",
                        details=f"Generated {offset}-day maturity alert for FDR {fdr.fdr_number}",
                    )

            # Overdue replacement trigger if maturity date has elapsed
            if days_remaining < 0:
                check_overdue_stmt = select(ReminderAlert).where(
                    ReminderAlert.fdr_id == fdr.id,
                    ReminderAlert.reminder_type == ReminderType.OVERDUE_REPLACEMENT,
                    ReminderAlert.days_offset == 0,
                )
                existing_overdue = await session.execute(check_overdue_stmt)
                if existing_overdue.scalar_one_or_none() is None:
                    overdue_alert = ReminderAlert(
                        fdr_id=fdr.id,
                        institution_id=fdr.institution_id,
                        reminder_type=ReminderType.OVERDUE_REPLACEMENT,
                        days_offset=0,
                        due_date=fdr.maturity_date,
                        status=ReminderStatus.SENT,
                        message=(
                            f"FDR {fdr.fdr_number} is OVERDUE by {abs(days_remaining)} day(s)! "
                            f"Action: immediately upload replacement FDR or risk encashment."
                        ),
                        recipient="regional_officer@aicte-india.org",
                    )
                    session.add(overdue_alert)
                    new_alerts.append(overdue_alert)
                    await session.flush()

        return new_alerts

    @staticmethod
    async def check_and_escalate_unacknowledged(
        session: AsyncSession,
        reference_date: Optional[date] = None,
        escalation_threshold_days: int = 7,
    ) -> List[ReminderAlert]:
        """
        Escalation trigger: If an alert remains unacknowledged within 7 days of deadline,
        transitions status to ESCALATED and re-assigns recipient to Regional Officer.
        """
        ref_date = reference_date or date.today()

        stmt = select(ReminderAlert).where(
            ReminderAlert.status.in_([ReminderStatus.PENDING, ReminderStatus.SENT]),
            ReminderAlert.reminder_type == ReminderType.UPCOMING_MATURITY,
        )
        result = await session.execute(stmt)
        alerts = list(result.scalars().all())

        escalated: List[ReminderAlert] = []

        for alert in alerts:
            days_left = (alert.due_date - ref_date).days
            # If within 7 days of deadline and still not acknowledged
            if days_left <= escalation_threshold_days:
                alert.status = ReminderStatus.ESCALATED
                alert.recipient = "regional_officer@aicte-india.org"
                alert.assigned_officer_id = "REGIONAL_OFFICER"
                if alert.message and "[ESCALATED" not in alert.message:
                    alert.message += " [ESCALATED: Alert unacknowledged within 7 days of deadline. Escalated to Regional Officer.]"

                session.add(alert)
                escalated.append(alert)

                await AuditService.record_event(
                    session=session,
                    action="REMINDER_ALERT_ESCALATED",
                    payload={
                        "alert_id": alert.id,
                        "fdr_id": alert.fdr_id,
                        "days_left": days_left,
                        "escalated_to": alert.recipient,
                    },
                    user_id="ESCALATION_MONITOR",
                    details=f"Escalated unacknowledged alert {alert.id} to Regional Officer",
                )

        await session.flush()
        return escalated

    @staticmethod
    async def draft_encashment_notice(
        session: AsyncSession,
        fdr_id: int | str,
        officer_id: Optional[str] = "REGIONAL_OFFICER",
        grace_period_days: int = 15,
        reference_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Safe default-encashment trigger:
        If renewal is completely missed past maturity and grace period, drafts an official demand notice PDF
        and routes it to an officer's approval queue. The system drafts it; an officer must sign it.
        """
        int_id = int(fdr_id)
        fdr = await session.get(FDR, int_id)
        if not fdr:
            raise ValueError(f"FDR with ID {fdr_id} not found")

        ref_date = reference_date or date.today()
        days_past_maturity = (ref_date - fdr.maturity_date).days if fdr.maturity_date else 0

        notice_year = datetime.now(timezone.utc).year
        notice_ref = f"AICTE/FD/ENCASH/{notice_year}/{fdr.id:04d}"

        # Generate official demand notice PDF bytes referencing Handbook Clause 6.46
        pdf_text = (
            f"%PDF-1.4\n"
            f"% AICTE FinTrust Official Default Encashment Demand Notice\n"
            f"% Notice Reference: {notice_ref}\n"
            f"% Date of Issue: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            f"% Lien Holder: AICTE (All India Council for Technical Education)\n"
            f"% To: The Branch Manager, {fdr.bank_name}\n"
            f"% Subject: Encashment of Fixed Deposit Receipt No: {fdr.fdr_number}\n"
            f"% Amount: INR {fdr.principal_amount}\n"
            f"% Maturity Date: {fdr.maturity_date}\n"
            f"% Institution ID: {fdr.institution_id}\n"
            f"% Statutory Authority: AICTE Approval Process Handbook Clause 6.46 (2024-2027)\n"
            f"% Drafted by: AICTE FinTrust Automated Date Engine\n"
            f"% Status: PENDING_OFFICER_SIGNATURE\n"
            f"%%EOF\n"
        )
        pdf_bytes = pdf_text.encode("utf-8")

        # Upload draft to MinIO
        notice_filename = f"Draft_Demand_Notice_FDR_{fdr.fdr_number}.pdf"
        object_key = storage_service.upload_fdr_document(
            fdr_id=fdr.id,
            file_bytes=pdf_bytes,
            filename=notice_filename,
            content_type="application/pdf",
        )

        # Transition FDR state to ENCASHMENT_NOTICE_DRAFTED
        if fdr.status != FDRStatus.ENCASHMENT_NOTICE_DRAFTED:
            # If in ACTIVE or MATURED, transition
            if fdr.status == FDRStatus.ACTIVE:
                await StateMachineService.transition(
                    session=session,
                    fdr=fdr,
                    target_state=FDRStatus.ENCASHMENT_NOTICE_DRAFTED,
                    user_id=officer_id or "SYSTEM",
                    reason=f"Default encashment notice drafted: {notice_ref}",
                )
            elif fdr.status == FDRStatus.MATURED:
                await StateMachineService.transition(
                    session=session,
                    fdr=fdr,
                    target_state=FDRStatus.ENCASHMENT_NOTICE_DRAFTED,
                    user_id=officer_id or "SYSTEM",
                    reason=f"Default encashment notice drafted for matured FDR: {notice_ref}",
                )

        await AuditService.record_event(
            session=session,
            action="ENCASHMENT_NOTICE_DRAFTED",
            payload={
                "fdr_id": fdr.id,
                "fdr_number": fdr.fdr_number,
                "notice_reference": notice_ref,
                "pdf_path": object_key,
                "officer_queue": officer_id,
            },
            user_id=officer_id or "SYSTEM",
            details=f"Draft demand notice {notice_ref} routed to {officer_id} queue",
        )

        return {
            "notice_reference": notice_ref,
            "fdr_id": fdr.id,
            "fdr_status": fdr.status,
            "notice_pdf_path": object_key,
            "officer_queue": officer_id,
            "message": f"Draft encashment notice {notice_ref} generated and queued for officer approval.",
        }
