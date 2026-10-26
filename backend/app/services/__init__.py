"""
AICTE FinTrust Backend Services Module
Cleanly exports all domain and infrastructure services across auditing, state transitions,
document storage, forensic OCR, reminder engines, digital NOC generation, and bank adapters.
"""

from app.services.audit_service import (
    GENESIS_HASH,
    AuditService,
    compute_audit_hash,
    hash_payload,
    normalize_timestamp,
)
from app.services.bank_adapter import (
    BankAdapterInterface,
    BankConfirmationPayload,
    BankConfirmationResult,
    SFMSAdapter,
    SignedLinkAdapter,
    SimulatedBankAdapter,
)
from app.services.noc_service import (
    NOCService,
    generate_release_payload,
    sign_payload,
    verify_signature,
)
from app.services.ocr_forensics import OCRForensicService
from app.services.ocr_service import OCRService
from app.services.reminder_service import (
    DEFAULT_OFFSETS,
    ReminderService,
)
from app.services.state_machine import (
    ALLOWED_TRANSITIONS,
    FDRStateMachine,
    InvalidStateTransitionError,
    StateMachine,
    StateMachineService,
)
from app.services.storage_service import (
    StorageService,
    storage_service,
)

__all__ = [
    # Audit Ledger
    "AuditService",
    "compute_audit_hash",
    "hash_payload",
    "normalize_timestamp",
    "GENESIS_HASH",
    # State Machine
    "StateMachineService",
    "StateMachine",
    "FDRStateMachine",
    "InvalidStateTransitionError",
    "ALLOWED_TRANSITIONS",
    # Storage Service
    "StorageService",
    "storage_service",
    # Reminder Engine
    "ReminderService",
    "DEFAULT_OFFSETS",
    # NOC Generation & Cryptographic Verification
    "NOCService",
    "sign_payload",
    "verify_signature",
    "generate_release_payload",
    # Forensics & OCR
    "OCRService",
    "OCRForensicService",
    # Bank Adapters
    "BankAdapterInterface",
    "SimulatedBankAdapter",
    "SignedLinkAdapter",
    "SFMSAdapter",
    "BankConfirmationPayload",
    "BankConfirmationResult",
]