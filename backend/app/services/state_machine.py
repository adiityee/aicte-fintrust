from typing import Callable, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clearance import Clearance, ClearanceCell, ClearanceStatus
from app.models.fdr import FDR, FDRStatus
from app.services.audit_service import AuditService


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state machine transition is attempted."""

    def __init__(self, from_state: FDRStatus, to_state: FDRStatus, reason: str):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"Invalid FDR state transition from '{from_state.value}' to '{to_state.value}': {reason}"
        )


# Table of allowed state transitions as per ARCHITECTURE_PLAN.md
ALLOWED_TRANSITIONS: Dict[FDRStatus, Set[FDRStatus]] = {
    FDRStatus.DRAFT: {
        FDRStatus.SUBMITTED,
        FDRStatus.DRAFT,
    },
    FDRStatus.SUBMITTED: {
        FDRStatus.UNDER_SCRUTINY,
        FDRStatus.DRAFT,
    },
    FDRStatus.UNDER_SCRUTINY: {
        FDRStatus.QUERY_RAISED,
        FDRStatus.BANK_VERIFICATION_PENDING,
        FDRStatus.DRAFT,
    },
    FDRStatus.QUERY_RAISED: {
        FDRStatus.UNDER_SCRUTINY,
    },
    FDRStatus.BANK_VERIFICATION_PENDING: {
        FDRStatus.BANK_VERIFIED,
        FDRStatus.UNDER_SCRUTINY,
    },
    FDRStatus.BANK_VERIFIED: {
        FDRStatus.ACTIVE,
        FDRStatus.RELEASE_REQUESTED,
    },
    FDRStatus.ACTIVE: {
        FDRStatus.MATURED,
        FDRStatus.RENEWED,
        FDRStatus.RELEASE_REQUESTED,
        FDRStatus.ENCASHMENT_NOTICE_DRAFTED,
    },
    FDRStatus.MATURED: {
        FDRStatus.RENEWED,
        FDRStatus.RELEASE_REQUESTED,
        FDRStatus.ENCASHMENT_NOTICE_DRAFTED,
    },
    FDRStatus.RENEWED: {
        FDRStatus.ACTIVE,
        FDRStatus.RELEASE_REQUESTED,
    },
    FDRStatus.ENCASHMENT_NOTICE_DRAFTED: {
        FDRStatus.ACTIVE,
        FDRStatus.RELEASED,
    },
    FDRStatus.RELEASE_REQUESTED: {
        FDRStatus.CLEARANCES_APPROVED,
        FDRStatus.ACTIVE,
    },
    FDRStatus.CLEARANCES_APPROVED: {
        FDRStatus.RELEASED,
        FDRStatus.ACTIVE,
    },
    FDRStatus.RELEASED: set(),  # Terminal state
}


def guard_submitted(fdr: FDR) -> Tuple[bool, Optional[str]]:
    """Guard rule for transition to SUBMITTED: mandatory fields must be populated."""
    missing = []
    if not fdr.fdr_number or not fdr.fdr_number.strip():
        missing.append("fdr_number")
    if not fdr.bank_name or not fdr.bank_name.strip():
        missing.append("bank_name")
    if not fdr.ifsc_code or not fdr.ifsc_code.strip():
        missing.append("ifsc_code")
    if fdr.principal_amount is None or fdr.principal_amount <= 0:
        missing.append("principal_amount (must be > 0)")
    if fdr.issue_date is None:
        missing.append("issue_date")
    if fdr.maturity_date is None:
        missing.append("maturity_date")

    if missing:
        return False, f"Missing required fields for submission: {', '.join(missing)}"

    if fdr.issue_date and fdr.maturity_date and fdr.maturity_date <= fdr.issue_date:
        return False, "Maturity date must be strictly after issue date"

    return True, None


def guard_clearances_approved(fdr: FDR) -> Tuple[bool, Optional[str]]:
    """
    Guard rule for transition to CLEARANCES_APPROVED:
    All required clearance cells (PGRC, VIGILANCE, APPROVAL_BUREAU, LEGAL, FINANCE) must have APPROVED status.
    """
    if not hasattr(fdr, "clearances") or not fdr.clearances:
        return False, "No clearance records found for this FDR."

    required_cells = {
        ClearanceCell.PGRC,
        ClearanceCell.VIGILANCE,
        ClearanceCell.APPROVAL_BUREAU,
        ClearanceCell.LEGAL,
        ClearanceCell.FINANCE,
    }

    clearance_map = {c.cell_name: c.status for c in fdr.clearances}
    missing_cells = required_cells - set(clearance_map.keys())
    if missing_cells:
        cell_names = ", ".join(c.value for c in missing_cells)
        return False, f"Missing clearance task(s) for cell(s): {cell_names}"

    unapproved = [
        c.cell_name.value
        for c in fdr.clearances
        if c.cell_name in required_cells and c.status != ClearanceStatus.APPROVED
    ]

    if unapproved:
        return False, f"Clearance gate incomplete. Pending/rejected cell(s): {', '.join(unapproved)}"

    return True, None


def guard_released(fdr: FDR) -> Tuple[bool, Optional[str]]:
    """
    Guard rule for transition to RELEASED:
    Release must be preceded by CLEARANCES_APPROVED (or settlement of ENCASHMENT_NOTICE_DRAFTED).
    """
    if fdr.status not in (FDRStatus.CLEARANCES_APPROVED, FDRStatus.ENCASHMENT_NOTICE_DRAFTED):
        return (
            False,
            f"Release forbidden: current status '{fdr.status.value}' has not completed clearance approval gate.",
        )
    return True, None


# Guard mapping
GUARD_RULES: Dict[FDRStatus, Callable[[FDR], Tuple[bool, Optional[str]]]] = {
    FDRStatus.SUBMITTED: guard_submitted,
    FDRStatus.CLEARANCES_APPROVED: guard_clearances_approved,
    FDRStatus.RELEASED: guard_released,
}


class StateMachineService:
    """
    Service enforcing the lifecycle state transitions and guards
    for Fixed Deposit Receipts (FDRs).
    """

    @staticmethod
    def can_transition(fdr: FDR, target_state: FDRStatus) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a transition from fdr.status to target_state is permitted by graph and guards.
        """
        current_state = fdr.status

        # Check allowed transition graph
        allowed_targets = ALLOWED_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_targets:
            return (
                False,
                f"Transition from '{current_state.value}' to '{target_state.value}' is not permitted by state machine.",
            )

        # Check guard rules if any exist for target state
        guard_fn = GUARD_RULES.get(target_state)
        if guard_fn:
            passed, reason = guard_fn(fdr)
            if not passed:
                return False, reason

        return True, None

    @staticmethod
    async def transition(
        session: AsyncSession,
        fdr: FDR,
        target_state: FDRStatus,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> FDR:
        """
        Executes a state transition on the FDR, enforcing guards and recording an immutable audit entry.
        """
        can_proceed, error_msg = StateMachineService.can_transition(fdr, target_state)
        if not can_proceed:
            raise InvalidStateTransitionError(fdr.status, target_state, error_msg or "Guard check failed")

        previous_state = fdr.status
        fdr.status = target_state
        session.add(fdr)
        await session.flush()

        # Record cryptographically chained audit log
        await AuditService.record_event(
            session=session,
            action="FDR_STATE_TRANSITION",
            payload={
                "fdr_id": fdr.id,
                "fdr_number": fdr.fdr_number,
                "from_state": previous_state.value,
                "to_state": target_state.value,
                "reason": reason or f"State transitioned to {target_state.value}",
            },
            user_id=user_id or "SYSTEM",
            details=f"Transitioned FDR {fdr.id} from {previous_state.value} to {target_state.value}",
        )

        return fdr
