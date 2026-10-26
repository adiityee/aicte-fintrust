import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest

from app.models.clearance import Clearance, ClearanceCell, ClearanceStatus
from app.models.fdr import FDR, FDRStatus
from app.services.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidStateTransitionError,
    StateMachineService,
)
from tests.test_audit_service import MockAuditSession


def create_sample_fdr(status: FDRStatus = FDRStatus.DRAFT) -> FDR:
    return FDR(
        id=1,
        institution_id=10,
        fdr_number="SBI-2026-FDR-001",
        bank_name="State Bank of India",
        ifsc_code="SBIN0001234",
        principal_amount=Decimal("1500000.00"),
        interest_rate=Decimal("7.50"),
        issue_date=date(2026, 1, 1),
        maturity_date=date(2031, 1, 1),
        lien_holder="AICTE",
        status=status,
    )


def test_allowed_transitions_graph():
    # Verify valid forward progression
    fdr = create_sample_fdr(FDRStatus.DRAFT)
    assert StateMachineService.can_transition(fdr, FDRStatus.SUBMITTED)[0] is True

    fdr.status = FDRStatus.SUBMITTED
    assert StateMachineService.can_transition(fdr, FDRStatus.UNDER_SCRUTINY)[0] is True

    fdr.status = FDRStatus.UNDER_SCRUTINY
    assert StateMachineService.can_transition(fdr, FDRStatus.BANK_VERIFICATION_PENDING)[0] is True
    assert StateMachineService.can_transition(fdr, FDRStatus.QUERY_RAISED)[0] is True

    fdr.status = FDRStatus.QUERY_RAISED
    assert StateMachineService.can_transition(fdr, FDRStatus.UNDER_SCRUTINY)[0] is True

    fdr.status = FDRStatus.BANK_VERIFICATION_PENDING
    assert StateMachineService.can_transition(fdr, FDRStatus.BANK_VERIFIED)[0] is True

    fdr.status = FDRStatus.BANK_VERIFIED
    assert StateMachineService.can_transition(fdr, FDRStatus.ACTIVE)[0] is True


def test_invalid_jumps_blocked():
    fdr = create_sample_fdr(FDRStatus.DRAFT)

    # Disallowed jumps from DRAFT
    assert StateMachineService.can_transition(fdr, FDRStatus.RELEASED)[0] is False
    assert StateMachineService.can_transition(fdr, FDRStatus.ACTIVE)[0] is False
    assert StateMachineService.can_transition(fdr, FDRStatus.CLEARANCES_APPROVED)[0] is False

    # Disallowed jumps from SUBMITTED
    fdr.status = FDRStatus.SUBMITTED
    assert StateMachineService.can_transition(fdr, FDRStatus.RELEASED)[0] is False
    assert StateMachineService.can_transition(fdr, FDRStatus.BANK_VERIFIED)[0] is False

    # Terminal state RELEASED cannot transition to anything
    fdr.status = FDRStatus.RELEASED
    assert StateMachineService.can_transition(fdr, FDRStatus.ACTIVE)[0] is False
    assert StateMachineService.can_transition(fdr, FDRStatus.DRAFT)[0] is False


def test_guard_submitted_validation():
    # Test missing mandatory fields
    incomplete_fdr = FDR(
        id=2,
        institution_id=10,
        status=FDRStatus.DRAFT,
        fdr_number="",  # Missing
        bank_name="HDFC",
    )
    can_submit, reason = StateMachineService.can_transition(incomplete_fdr, FDRStatus.SUBMITTED)
    assert can_submit is False
    assert "Missing required fields" in reason

    # Test invalid dates: maturity <= issue date
    invalid_dates_fdr = create_sample_fdr(FDRStatus.DRAFT)
    invalid_dates_fdr.issue_date = date(2026, 5, 1)
    invalid_dates_fdr.maturity_date = date(2026, 4, 1)  # Before issue date
    can_submit, reason = StateMachineService.can_transition(invalid_dates_fdr, FDRStatus.SUBMITTED)
    assert can_submit is False
    assert "Maturity date must be strictly after issue date" in reason


def test_guard_clearances_gate():
    fdr = create_sample_fdr(FDRStatus.RELEASE_REQUESTED)

    # 1. No clearances attached -> blocked
    fdr.clearances = []
    can_pass, reason = StateMachineService.can_transition(fdr, FDRStatus.CLEARANCES_APPROVED)
    assert can_pass is False
    assert "No clearance records found" in reason

    # 2. Only 3 of 5 cells approved -> blocked
    fdr.clearances = [
        Clearance(id=1, fdr_id=fdr.id, cell_name=ClearanceCell.PGRC, status=ClearanceStatus.APPROVED),
        Clearance(id=2, fdr_id=fdr.id, cell_name=ClearanceCell.VIGILANCE, status=ClearanceStatus.APPROVED),
        Clearance(id=3, fdr_id=fdr.id, cell_name=ClearanceCell.LEGAL, status=ClearanceStatus.PENDING),
    ]
    can_pass, reason = StateMachineService.can_transition(fdr, FDRStatus.CLEARANCES_APPROVED)
    assert can_pass is False
    assert "Missing clearance task" in reason or "Clearance gate incomplete" in reason

    # 3. All 5 cells approved -> allowed
    fdr.clearances = [
        Clearance(id=1, fdr_id=fdr.id, cell_name=ClearanceCell.PGRC, status=ClearanceStatus.APPROVED),
        Clearance(id=2, fdr_id=fdr.id, cell_name=ClearanceCell.VIGILANCE, status=ClearanceStatus.APPROVED),
        Clearance(id=3, fdr_id=fdr.id, cell_name=ClearanceCell.APPROVAL_BUREAU, status=ClearanceStatus.APPROVED),
        Clearance(id=4, fdr_id=fdr.id, cell_name=ClearanceCell.LEGAL, status=ClearanceStatus.APPROVED),
        Clearance(id=5, fdr_id=fdr.id, cell_name=ClearanceCell.FINANCE, status=ClearanceStatus.APPROVED),
    ]
    can_pass, reason = StateMachineService.can_transition(fdr, FDRStatus.CLEARANCES_APPROVED)
    assert can_pass is True
    assert reason is None


def test_transition_execution_and_audit():
    async def _test():
        session = MockAuditSession()
        fdr = create_sample_fdr(FDRStatus.DRAFT)

        # Transition DRAFT -> SUBMITTED
        updated_fdr = await StateMachineService.transition(
            session=session,
            fdr=fdr,
            target_state=FDRStatus.SUBMITTED,
            user_id="OFFICER_01",
            reason="Submitted for testing",
        )
        assert updated_fdr.status == FDRStatus.SUBMITTED
        audit_records = [r for r in session.records if hasattr(r, "action")]
        assert len(audit_records) == 1
        assert audit_records[0].action == "FDR_STATE_TRANSITION"

        # Invalid transition raises InvalidStateTransitionError
        with pytest.raises(InvalidStateTransitionError):
            await StateMachineService.transition(
                session=session,
                fdr=fdr,
                target_state=FDRStatus.RELEASED,  # Blocked!
            )

    asyncio.run(_test())
