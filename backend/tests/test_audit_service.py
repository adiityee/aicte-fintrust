import asyncio
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, List, Optional
import pytest

from app.models.audit import AuditLog
from app.services.audit_service import (
    GENESIS_HASH,
    AuditService,
    compute_audit_hash,
    hash_payload,
    normalize_timestamp,
)


class MockResult:
    def __init__(self, scalar_value: Optional[str] = None, items: Optional[List[AuditLog]] = None):
        self._scalar = scalar_value
        self._items = items or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class MockAuditSession:
    """Mock AsyncSession for audit ledger testing without external database dependencies."""

    def __init__(self):
        self.records: List[AuditLog] = []
        self._next_id = 1

    def add(self, obj: AuditLog) -> None:
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = self._next_id
            self._next_id += 1
        if obj not in self.records:
            self.records.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def execute(self, statement) -> Any:
        sql = str(statement).lower()
        if "desc" in sql:
            # Query for latest hash: select(AuditLog.current_hash).order_by(AuditLog.id.desc()).limit(1)
            latest = self.records[-1].current_hash if self.records else None
            return MockResult(scalar_value=latest)
        else:
            # Query for all logs: select(AuditLog).order_by(AuditLog.id.asc())
            sorted_records = sorted(self.records, key=lambda r: r.id)
            return MockResult(items=sorted_records)


def test_genesis_hash_format():
    assert len(GENESIS_HASH) == 64
    assert GENESIS_HASH == "0" * 64


def test_compute_audit_hash_formula():
    prev_hash = "0" * 64
    action = "FDR_SUBMITTED"
    payload_hash = hashlib.sha256(b"sample_fdr_payload").hexdigest()
    user_id = "INSTITUTION_USER_42"
    timestamp = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)

    # Compute using function
    computed = compute_audit_hash(
        previous_hash=prev_hash,
        action=action,
        payload_hash=payload_hash,
        user_id=user_id,
        timestamp=timestamp,
    )

    # Compute manually following formula H_n = SHA256(H_{n-1} + action + payload_hash + user_id + timestamp)
    expected_raw = f"{prev_hash}{action}{payload_hash}{user_id}{timestamp.isoformat()}"
    expected = hashlib.sha256(expected_raw.encode("utf-8")).hexdigest()

    assert computed == expected


def test_hash_payload_deterministic():
    dict1 = {"bank": "SBI", "amount": 1000000, "fdr_no": "FDR123"}
    dict2 = {"fdr_no": "FDR123", "amount": 1000000, "bank": "SBI"}  # Different order

    assert hash_payload(dict1) == hash_payload(dict2)
    assert len(hash_payload(dict1)) == 64


async def _run_audit_chain_test():
    session = MockAuditSession()

    # 1. Verify empty chain integrity
    empty_res = await AuditService.verify_chain_integrity(session)
    assert empty_res["is_valid"] is True
    assert empty_res["total_records"] == 0

    # 2. Add Event 1 (Genesis block)
    log1 = await AuditService.record_event(
        session=session,
        action="INSTITUTION_REGISTERED",
        payload={"name": "College A"},
        user_id="ADMIN_1",
    )
    assert log1.previous_hash == GENESIS_HASH
    assert log1.current_hash is not None

    # 3. Add Event 2 (Chain block 2)
    log2 = await AuditService.record_event(
        session=session,
        action="FDR_DEPOSITED",
        payload={"fdr_number": "SBI-1001", "amount": 500000},
        user_id="INST_USER_1",
    )
    assert log2.previous_hash == log1.current_hash

    # 4. Add Event 3 (Chain block 3)
    log3 = await AuditService.record_event(
        session=session,
        action="SCRUTINY_PASSED",
        payload={"status": "UNDER_SCRUTINY"},
        user_id="OFFICER_1",
    )
    assert log3.previous_hash == log2.current_hash

    # 5. Verify chain integrity when unhampered
    verification = await AuditService.verify_chain_integrity(session)
    assert verification["is_valid"] is True
    assert verification["total_records"] == 3
    assert len(verification["broken_links"]) == 0

    # 6. Tamper simulation: directly edit block 2 action in DB
    log2.action = "FDR_TAMPERED_ACTION"

    # 7. Run verification again -> must flag broken links
    tampered_verification = await AuditService.verify_chain_integrity(session)
    assert tampered_verification["is_valid"] is False
    assert len(tampered_verification["broken_links"]) > 0

    tampered_entry = tampered_verification["broken_links"][0]
    assert tampered_entry["record_id"] == log2.id
    issues = [iss["issue"] for iss in tampered_entry["issues"]]
    assert "CURRENT_HASH_CORRUPTED_OR_TAMPERED" in issues


def test_audit_service_chaining_and_tamper_detection():
    asyncio.run(_run_audit_chain_test())
