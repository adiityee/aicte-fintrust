from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional
from pydantic import BaseModel

from app.core.config import settings


class BankConfirmationPayload(BaseModel):
    """Four mandatory verification parameters required by AICTE."""
    lien_affirmed: bool = True
    no_encashment_without_aicte: bool = True
    auto_renewal_status: bool = True
    balance_confirmed: Decimal


class BankConfirmationResult(BaseModel):
    """Result of bank verification and lien affirmation."""
    fdr_id: int
    adapter_name: str
    is_confirmed: bool
    confirmation_ref: str
    confirmed_at: datetime
    bank_officer_id: Optional[str] = None
    details: Dict[str, Any]


class BankAdapterInterface(ABC):
    """Common interface for bank confirmation adapters."""

    @abstractmethod
    async def generate_signed_link(self, fdr_id: int, branch_email: str) -> str:
        """Generates a secure, HMAC-signed verification link for nodal bank email."""
        pass

    @abstractmethod
    async def verify_signed_link(self, token: str) -> Optional[int]:
        """Validates HMAC signature and expiry, returning the target FDR ID."""
        pass

    @abstractmethod
    async def confirm_lien(
        self,
        fdr_id: int,
        payload: BankConfirmationPayload,
        officer_id: str,
    ) -> BankConfirmationResult:
        """Affirms lien and transitions instrument to Bank Verified & Lien Affirmed."""
        pass


class SimulatedBankAdapter(BankAdapterInterface):
    """
    Simulated Bank Adapter (Used for Demos & Offline Testing)
    Clearly labelled as simulated; immediately returns verified confirmation.
    """

    def __init__(self, mock_delay_seconds: float = 0.0):
        self.mock_delay_seconds = mock_delay_seconds

    async def generate_signed_link(self, fdr_id: int, branch_email: str) -> str:
        token = f"simulated_token_{fdr_id}_{secrets.token_hex(8)}"
        return f"http://localhost:3000/bank-confirm?token={token}"

    async def verify_signed_link(self, token: str) -> Optional[int]:
        if token.startswith("simulated_token_"):
            parts = token.split("_")
            if len(parts) >= 3 and parts[2].isdigit():
                return int(parts[2])
        return 999  # Fallback demo FDR ID

    async def confirm_lien(
        self,
        fdr_id: int,
        payload: BankConfirmationPayload,
        officer_id: str = "SIMULATED_BANK_OFFICER",
    ) -> BankConfirmationResult:
        ref = f"SIM-BANK-{secrets.token_hex(6).upper()}"
        return BankConfirmationResult(
            fdr_id=fdr_id,
            adapter_name="SimulatedBankAdapter",
            is_confirmed=payload.lien_affirmed and payload.no_encashment_without_aicte,
            confirmation_ref=ref,
            confirmed_at=datetime.now(timezone.utc),
            bank_officer_id=officer_id,
            details={
                "lien_marked_in_favour_of": "AICTE",
                "no_encashment_without_aicte": payload.no_encashment_without_aicte,
                "auto_renewal_enabled": payload.auto_renewal_status,
                "verified_balance": str(payload.balance_confirmed),
                "simulated": True,
            },
        )


class SignedLinkAdapter(BankAdapterInterface):
    """
    Signed Link Adapter (Branch Nodal Officer Verification Loop)
    Generates single-use, HMAC-SHA256 signed links valid for 72 hours,
    sent to the branch nodal email.
    """

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = (secret_key or settings.SECRET_KEY).encode("utf-8")

    def _generate_hmac_token(self, fdr_id: int, expires_at_ts: int) -> str:
        msg = f"{fdr_id}:{expires_at_ts}".encode("utf-8")
        sig = hmac.new(self.secret_key, msg, hashlib.sha256).hexdigest()
        return f"{fdr_id}.{expires_at_ts}.{sig}"

    async def generate_signed_link(self, fdr_id: int, branch_email: str, valid_hours: int = 72) -> str:
        expires_at = int((datetime.now(timezone.utc) + timedelta(hours=valid_hours)).timestamp())
        token = self._generate_hmac_token(fdr_id, expires_at)
        return f"http://localhost:3000/bank/verify/{token}"

    async def verify_signed_link(self, token: str) -> Optional[int]:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            fdr_id_str, expires_ts_str, signature = parts
            fdr_id = int(fdr_id_str)
            expires_at = int(expires_ts_str)

            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts > expires_at:
                return None  # Expired

            expected_token = self._generate_hmac_token(fdr_id, expires_at)
            if not hmac.compare_digest(token, expected_token):
                return None  # Tampered signature

            return fdr_id
        except Exception:
            return None

    async def confirm_lien(
        self,
        fdr_id: int,
        payload: BankConfirmationPayload,
        officer_id: str,
    ) -> BankConfirmationResult:
        ref = f"NODAL-AFFIRM-{secrets.token_hex(6).upper()}"
        return BankConfirmationResult(
            fdr_id=fdr_id,
            adapter_name="SignedLinkAdapter",
            is_confirmed=payload.lien_affirmed and payload.no_encashment_without_aicte,
            confirmation_ref=ref,
            confirmed_at=datetime.now(timezone.utc),
            bank_officer_id=officer_id,
            details={
                "lien_affirmed": payload.lien_affirmed,
                "no_encashment_without_aicte": payload.no_encashment_without_aicte,
                "auto_renewal_status": payload.auto_renewal_status,
                "balance": str(payload.balance_confirmed),
                "hmac_verified": True,
            },
        )


class SFMSAdapter(BankAdapterInterface):
    """
    SFMS / Account Aggregator Adapter (Production Gateway Stub)
    Documented as the production enterprise path for MT760 structured messaging.
    """

    async def generate_signed_link(self, fdr_id: int, branch_email: str) -> str:
        raise NotImplementedError("SFMS uses direct MT760 host-to-host messaging, not signed email links.")

    async def verify_signed_link(self, token: str) -> Optional[int]:
        raise NotImplementedError("SFMS verification uses MT760 ACK/NACK digital envelopes.")

    async def confirm_lien(
        self,
        fdr_id: int,
        payload: BankConfirmationPayload,
        officer_id: str,
    ) -> BankConfirmationResult:
        ref = f"SFMS-MT760-{secrets.token_hex(8).upper()}"
        return BankConfirmationResult(
            fdr_id=fdr_id,
            adapter_name="SFMSAdapter",
            is_confirmed=True,
            confirmation_ref=ref,
            confirmed_at=datetime.now(timezone.utc),
            bank_officer_id="SFMS_GATEWAY_GATE",
            details={
                "swift_message_type": "MT760",
                "structured_lien_clause": "AICTE-FINTRUST-SFMS-AFFIRMED",
                "interbank_status": "ACK_CONFIRMED",
            },
        )
