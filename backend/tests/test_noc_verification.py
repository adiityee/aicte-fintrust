from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.clearance import Clearance, ClearanceCell, ClearanceStatus
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.services.noc_service import (
    NOCService,
    canonical_payload_bytes,
    generate_noc_pdf,
    generate_release_payload,
    get_public_key_hex,
    sign_payload,
    verify_signature,
)
from app.services.storage_service import storage_service


# ---------------------------------------------------------------------------
# Unit Tests for Cryptographic Signing & PDF Generation
# ---------------------------------------------------------------------------

def test_ed25519_sign_and_verify_valid():
    sample_fdr = FDR(
        id=99,
        institution_id=1,
        bank_name="State Bank of India",
        principal_amount=Decimal("1500000.00"),
    )
    payload = generate_release_payload(
        fdr=sample_fdr,
        release_date_str="2026-10-26",
        officer_id="DIRECTOR_GENERAL_AICTE",
    )

    signature = sign_payload(payload)
    assert len(signature) == 128  # 64 bytes = 128 hex chars

    # Verifies cleanly
    assert verify_signature(payload, signature) is True


def test_ed25519_tamper_detection():
    sample_fdr = FDR(
        id=99,
        institution_id=1,
        bank_name="State Bank of India",
        principal_amount=Decimal("1500000.00"),
    )
    payload = generate_release_payload(
        fdr=sample_fdr,
        release_date_str="2026-10-26",
        officer_id="DIRECTOR_GENERAL_AICTE",
    )
    signature = sign_payload(payload)

    # Tamper payload: fraudulently inflate principal amount
    tampered_payload = dict(payload)
    tampered_payload["principal_amount"] = "2500000.00"

    assert verify_signature(tampered_payload, signature) is False

    # Tamper payload: change date
    tampered_date_payload = dict(payload)
    tampered_date_payload["release_authorization_date"] = "2026-11-01"

    assert verify_signature(tampered_date_payload, signature) is False


def test_generate_noc_pdf_with_qr():
    sample_fdr = FDR(
        id=101,
        institution_id=1,
        fdr_number="SBI-NOC-101",
        bank_name="State Bank of India",
        ifsc_code="SBIN0001234",
        principal_amount=Decimal("1000000.00"),
        interest_rate=Decimal("7.25"),
        issue_date=date(2021, 1, 1),
        maturity_date=date(2026, 1, 1),
        status=FDRStatus.RELEASED,
    )
    payload = generate_release_payload(
        fdr=sample_fdr,
        release_date_str="2026-10-26",
        officer_id="MEMBER_SECRETARY_AICTE",
    )
    signature = sign_payload(payload)

    pdf_bytes = generate_noc_pdf(
        fdr=sample_fdr,
        payload=payload,
        signature_hex=signature,
        officer_id="MEMBER_SECRETARY_AICTE",
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert len(pdf_bytes) > 2000


# ---------------------------------------------------------------------------
# Integration Tests for Release Gate Approval & Public Verification Endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
async def client_session():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with test_async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, test_async_session

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_approve_release_gate_locked_when_unapproved(client_session):
    client, session_maker = client_session

    async with session_maker() as session:
        inst = Institution(
            id=70,
            aicte_permanent_id="AICTE-70",
            name="Delhi Polytechnic Institute",
            state="Delhi",
            email="registrar@dpi.edu",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=400,
            institution_id=70,
            fdr_number="PNB-REL-400",
            bank_name="Punjab National Bank",
            ifsc_code="PUNB0001111",
            principal_amount=Decimal("1000000.00"),
            interest_rate=Decimal("7.0"),
            issue_date=date(2021, 1, 1),
            maturity_date=date(2026, 1, 1),
            status=FDRStatus.RELEASE_REQUESTED,
        )
        session.add(fdr)
        await session.flush()

        # Only 2 clearances exist and are still PENDING
        c1 = Clearance(fdr_id=400, cell_name=ClearanceCell.PGRC, status=ClearanceStatus.PENDING)
        c2 = Clearance(fdr_id=400, cell_name=ClearanceCell.VIGILANCE, status=ClearanceStatus.PENDING)
        session.add(c1)
        session.add(c2)
        await session.commit()

    # Attempt final release approval: must be blocked with HTTP 400
    res = await client.post("/api/v1/clearance/400/approve-release?officer_id=MEMBER_SECRETARY")
    assert res.status_code == 400
    assert "Release gate locked" in res.json()["detail"]


@pytest.mark.asyncio
async def test_approve_release_success_and_public_verification(client_session):
    client, session_maker = client_session

    # 1. Setup fully cleared FDR in DB
    async with session_maker() as session:
        inst = Institution(
            id=71,
            aicte_permanent_id="AICTE-71",
            name="IIT Mumbai Excellence Center",
            state="Maharashtra",
            email="admin@iitme.edu",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=401,
            institution_id=71,
            fdr_number="SBI-CLEAR-401",
            bank_name="State Bank of India",
            ifsc_code="SBIN0005555",
            principal_amount=Decimal("3000000.00"),
            interest_rate=Decimal("7.50"),
            issue_date=date(2021, 5, 1),
            maturity_date=date(2026, 5, 1),
            status=FDRStatus.RELEASE_REQUESTED,
        )
        session.add(fdr)
        await session.flush()

        # Add all 5 clearance cells as APPROVED
        cells = [
            ClearanceCell.PGRC,
            ClearanceCell.VIGILANCE,
            ClearanceCell.APPROVAL_BUREAU,
            ClearanceCell.LEGAL,
            ClearanceCell.FINANCE,
        ]
        for cell in cells:
            session.add(
                Clearance(
                    fdr_id=401,
                    cell_name=cell,
                    status=ClearanceStatus.APPROVED,
                    officer_id=f"OFFICER_{cell.value}",
                    remarks="All prerequisites verified.",
                )
            )
        await session.commit()

    with patch.object(
        storage_service,
        "upload_fdr_document",
        return_value="nocs/401/NOC_AICTE_401_SBI-CLEAR-401.pdf",
    ), patch.object(
        storage_service,
        "generate_presigned_url",
        return_value="https://minio.local/noc-certificates/nocs/401/NOC.pdf?expires=300",
    ):
        # 2. Competent Authority authorizes release
        rel_res = await client.post(
            "/api/v1/clearance/401/approve-release?officer_id=COMPETENT_AUTHORITY_DIR"
        )
        assert rel_res.status_code == 200
        rel_data = rel_res.json()
        assert rel_data["fdr_status"] == "RELEASED"
        assert rel_data["noc_document_path"] == "nocs/401/NOC_AICTE_401_SBI-CLEAR-401.pdf"
        assert len(rel_data["ed25519_signature"]) == 128
        assert "http://localhost:3000/verify/401" in rel_data["public_verification_url"]

        # 3. Verify audit ledger entry in DB
        async with session_maker() as session:
            audit_res = await session.execute(
                select(AuditLog).where(AuditLog.action == "RELEASE_AUTHORIZED_NOC_ISSUED")
            )
            audit_log = audit_res.scalar_one()
            assert audit_log is not None
            assert audit_log.user_id == "COMPETENT_AUTHORITY_DIR"

        # 4. Public QR code verification endpoint GET /api/v1/verify/401
        verify_res = await client.get("/api/v1/verify/401")
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["fdr_id"] == 401
        assert verify_data["fdr_status"] == "RELEASED"
        assert verify_data["is_released"] is True
        assert verify_data["is_signature_valid"] is True
        assert verify_data["signature_algorithm"] == "Ed25519 (RFC 8032)"
        assert len(verify_data["clearances"]) == 5
        assert "cryptographically valid" in verify_data["message"]
        assert "minio.local" in verify_data["noc_download_url"]

        # 5. Tamper verification check: alter the signature in the DB
        async with session_maker() as session:
            fdr_in_db = await session.get(FDR, 401)
            fdr_in_db.noc_signature = "0" * 128  # Invalid signature
            session.add(fdr_in_db)
            await session.commit()

        # Re-verify -> Must catch the fraudulent signature
        tampered_verify_res = await client.get("/api/v1/verify/401")
        assert tampered_verify_res.status_code == 200
        tampered_verify_data = tampered_verify_res.json()
        assert tampered_verify_data["is_signature_valid"] is False
        assert "TAMPER WARNING" in tampered_verify_data["message"]
