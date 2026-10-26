"""Bank confirmation adapter interface and demo-safe implementations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlencode


class BaseBankAdapter(ABC):
    @abstractmethod
    def request_confirmation(self, fdr_id: str, **details: Any) -> dict[str, Any]:
        """Start bank confirmation and return an adapter-specific payload."""


class SimulatedBankAdapter(BaseBankAdapter):
    def request_confirmation(self, fdr_id: str, **details: Any) -> dict[str, Any]:
        return {
            "fdr_id": fdr_id,
            "status": "confirmed",
            "simulated": True,
            "utr": f"SIM{secrets.randbelow(10**12):012d}",
            "lien_status": "affirmed",
            "message": "Simulated bank confirmation; not an actual bank response.",
        }


class SignedLinkAdapter(BaseBankAdapter):
    """Issue signed branch-verification links, single-use per process instance."""

    def __init__(
        self,
        base_url: str,
        signing_secret: str | bytes,
        expiration_seconds: int = 24 * 60 * 60,
    ) -> None:
        if not signing_secret:
            raise ValueError("A non-empty signing secret is required.")
        if not 1 <= expiration_seconds <= 24 * 60 * 60:
            raise ValueError("Link expiration must be between 1 second and 24 hours.")
        self.base_url = base_url.rstrip("/")
        self._secret = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
        self.expiration_seconds = expiration_seconds
        self._used_nonces: set[str] = set()
        self._lock = threading.Lock()

    def _signature(self, encoded_payload: str) -> str:
        return hmac.new(self._secret, encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()

    def request_confirmation(self, fdr_id: str, **details: Any) -> dict[str, Any]:
        now = int(time.time())
        payload = {
            "fdr_id": fdr_id,
            "issued_at": now,
            "expires_at": now + self.expiration_seconds,
            "nonce": secrets.token_urlsafe(18),
            "details": details,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        encoded = base64.urlsafe_b64encode(serialized).decode("ascii").rstrip("=")
        signature = self._signature(encoded)
        link = f"{self.base_url}/verify/{encoded}?{urlencode({'sig': signature})}"
        return {
            "fdr_id": fdr_id,
            "status": "pending_branch_verification",
            "simulated": False,
            "verification_url": link,
            "expires_at": payload["expires_at"],
        }

    def consume_token(self, encoded_payload: str, signature: str) -> dict[str, Any] | None:
        """Validate and consume a signed payload; a replay returns ``None``."""
        if not hmac.compare_digest(self._signature(encoded_payload), signature):
            return None
        try:
            padded = encoded_payload + "=" * (-len(encoded_payload) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or int(payload.get("expires_at", 0)) < int(time.time()):
            return None
        nonce = payload.get("nonce")
        if not isinstance(nonce, str):
            return None
        with self._lock:
            if nonce in self._used_nonces:
                return None
            self._used_nonces.add(nonce)
        return payload