from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

# The standard 64-character genesis hash representing H_0
GENESIS_HASH: str = "0" * 64


def normalize_timestamp(ts: datetime | str) -> str:
    """
    Deterministically normalizes a datetime or timestamp string to ISO-8601 UTC string.
    """
    if isinstance(ts, str):
        return ts
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return ts.isoformat()


def hash_payload(payload: Any) -> str:
    """
    Computes a SHA-256 hash of a payload dictionary, string, or bytes.
    If the payload is already a 64-character hex string, it can be returned as is.
    """
    if payload is None:
        payload_data = b""
    elif isinstance(payload, bytes):
        payload_data = payload
    elif isinstance(payload, str):
        # If already a 64-char valid hex string, assume it's pre-computed
        if len(payload) == 64 and all(c in "0123456789abcdefABCDEF" for c in payload):
            return payload.lower()
        payload_data = payload.encode("utf-8")
    else:
        # Deterministic JSON serialization with sorted keys
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        payload_data = payload_str.encode("utf-8")

    return hashlib.sha256(payload_data).hexdigest()


def compute_audit_hash(
    previous_hash: str,
    action: str,
    payload_hash: str,
    user_id: Optional[str],
    timestamp: datetime | str,
) -> str:
    """
    Calculates the cryptographic block hash according to the formula:
    H_n = SHA256(H_{n-1} + action + payload_hash + user_id + timestamp)
    """
    user_id_str = str(user_id) if user_id is not None else "SYSTEM"
    timestamp_str = normalize_timestamp(timestamp)

    # Hash chaining concatenation: H_{n-1} + action + payload_hash + user_id + timestamp
    raw_message = f"{previous_hash}{action}{payload_hash}{user_id_str}{timestamp_str}"
    return hashlib.sha256(raw_message.encode("utf-8")).hexdigest()


class AuditService:
    """
    Audit Ledger Service
    Provides tamper-evident cryptographic hash chaining for all system actions
    and full integrity verification to detect any database tampering.
    """

    @staticmethod
    async def get_latest_hash(session: AsyncSession) -> str:
        """
        Retrieves the current_hash of the latest record in the audit chain,
        or returns the GENESIS_HASH if the ledger is empty.
        """
        query = select(AuditLog.current_hash).order_by(AuditLog.id.desc()).limit(1)
        result = await session.execute(query)
        latest_hash = result.scalar_one_or_none()
        return latest_hash if latest_hash is not None else GENESIS_HASH

    @staticmethod
    async def record_event(
        session: AsyncSession,
        action: str,
        payload: Any = None,
        payload_hash: Optional[str] = None,
        user_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        details: Optional[str] = None,
    ) -> AuditLog:
        """
        Records an audit event in the tamper-evident chain:
        1. Fetches previous hash H_{n-1}
        2. Computes payload hash if needed
        3. Computes H_n = SHA256(H_{n-1} + action + payload_hash + user_id + timestamp)
        4. Inserts immutable record into DB
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        computed_payload_hash = payload_hash or hash_payload(payload)
        previous_hash = await AuditService.get_latest_hash(session)

        current_hash = compute_audit_hash(
            previous_hash=previous_hash,
            action=action,
            payload_hash=computed_payload_hash,
            user_id=user_id,
            timestamp=timestamp,
        )

        audit_entry = AuditLog(
            previous_hash=previous_hash,
            current_hash=current_hash,
            action=action,
            payload_hash=computed_payload_hash,
            user_id=user_id,
            timestamp=timestamp,
            details=details,
        )

        session.add(audit_entry)
        await session.flush()
        return audit_entry

    @staticmethod
    async def verify_chain_integrity(session: AsyncSession) -> Dict[str, Any]:
        """
        Walks the entire audit ledger sequentially from genesis block to tip.
        Verifies:
        1. Genesis record points to GENESIS_HASH
        2. Each record's previous_hash matches preceding record's current_hash
        3. Each record's current_hash matches SHA256(previous_hash + action + payload_hash + user_id + timestamp)

        Flags broken links or tampered entries.
        """
        query = select(AuditLog).order_by(AuditLog.id.asc())
        result = await session.execute(query)
        logs: List[AuditLog] = list(result.scalars().all())

        total_records = len(logs)
        broken_links: List[Dict[str, Any]] = []

        if total_records == 0:
            return {
                "is_valid": True,
                "total_records": 0,
                "broken_links": [],
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "message": "Audit chain is empty. Integrity intact.",
            }

        expected_previous_hash = GENESIS_HASH

        for idx, entry in enumerate(logs):
            entry_issues = []

            # Check 1: Chain continuity (previous_hash matches previous record's current_hash)
            if entry.previous_hash != expected_previous_hash:
                entry_issues.append({
                    "issue": "PREVIOUS_HASH_MISMATCH",
                    "expected_previous_hash": expected_previous_hash,
                    "actual_previous_hash": entry.previous_hash,
                })

            # Check 2: Content integrity (recompute H_n)
            recalculated_hash = compute_audit_hash(
                previous_hash=entry.previous_hash,
                action=entry.action,
                payload_hash=entry.payload_hash,
                user_id=entry.user_id,
                timestamp=entry.timestamp,
            )

            if entry.current_hash != recalculated_hash:
                entry_issues.append({
                    "issue": "CURRENT_HASH_CORRUPTED_OR_TAMPERED",
                    "expected_current_hash": recalculated_hash,
                    "actual_current_hash": entry.current_hash,
                })

            if entry_issues:
                broken_links.append({
                    "index": idx,
                    "record_id": entry.id,
                    "action": entry.action,
                    "user_id": entry.user_id,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "issues": entry_issues,
                })

            # For the next block, expect this block's current_hash
            expected_previous_hash = entry.current_hash

        is_valid = len(broken_links) == 0

        return {
            "is_valid": is_valid,
            "total_records": total_records,
            "broken_links": broken_links,
            "broken_links_count": len(broken_links),
            "first_record_id": logs[0].id if logs else None,
            "latest_record_id": logs[-1].id if logs else None,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "message": "Chain integrity verified successfully." if is_valid else f"Tampering detected! {len(broken_links)} broken link(s) found.",
        }
