from datetime import date, timedelta
from decimal import Decimal
import hashlib
from unittest.mock import MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.services.storage_service import StorageService, storage_service


# ---------------------------------------------------------------------------
# Unit Tests for StorageService
# ---------------------------------------------------------------------------

def test_storage_ensure_bucket_exists():
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False

    service = StorageService(bucket_name="test-fdr-docs")
    service._client = mock_client

    service.ensure_bucket_exists()
    mock_client.bucket_exists.assert_called_once_with("test-fdr-docs")
    mock_client.make_bucket.assert_called_once_with("test-fdr-docs")


def test_storage_upload_fdr_document_encryption():
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True

    service = StorageService(bucket_name="fdr-documents")
    service._client = mock_client

    file_bytes = b"%PDF-1.4 Mock FDR Content for AICTE Deposit"
    object_key = service.upload_fdr_document(
        fdr_id="999",
        file_bytes=file_bytes,
        filename="sbi_deposit.pdf",
        content_type="application/pdf",
    )

    assert object_key.startswith("fdrs/999/")
    assert object_key.endswith("sbi_deposit.pdf")

    # Assert put_object was called with SSE-S3 encryption
    mock_client.put_object.assert_called_once()
    _, kwargs = mock_client.put_object.call_args
    assert kwargs["bucket_name"] == "fdr-documents"
    assert kwargs["object_name"] == object_key
    assert kwargs["length"] == len(file_bytes)
    assert kwargs["content_type"] == "application/pdf"
    assert kwargs["sse"] is not None


def test_storage_generate_presigned_url():
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "https://minio.aicte.gov.in/fdr-documents/sample?token=xyz"

    service = StorageService(bucket_name="fdr-documents")
    service._client = mock_client

    # Test presigned URL generation with default 300s (under 5 mins)
    url = service.generate_presigned_url(
        object_key="fdrs/101/1700000000_fdr.pdf",
        expires_in_seconds=300,
    )
    assert url.startswith("https://minio.aicte.gov.in")
    mock_client.presigned_get_object.assert_called_once_with(
        bucket_name="fdr-documents",
        object_name="fdrs/101/1700000000_fdr.pdf",
        expires=timedelta(seconds=300),
    )

    # Test that expires_in_seconds > 300 is clamped to 300s
    service.generate_presigned_url("fdrs/101/doc.pdf", expires_in_seconds=900)
    _, kwargs = mock_client.presigned_get_object.call_args
    assert kwargs["expires"] == timedelta(seconds=300)


# ---------------------------------------------------------------------------
# API Tests for Document Upload, Download URL & Audit Verification
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
async def test_upload_fdr_document_and_download_url(client_session):
    client, session_maker = client_session

    # 1. Seed an institution and draft FDR in DB
    async with session_maker() as session:
        inst = Institution(
            id=30,
            aicte_permanent_id="AICTE-30",
            name="Pune Institute of Tech",
            state="Maharashtra",
            email="registrar@pit.edu.in",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=200,
            institution_id=30,
            fdr_number="BOB-FDR-200",
            bank_name="Bank of Baroda",
            ifsc_code="BARB0001234",
            principal_amount=Decimal("1200000.00"),
            interest_rate=Decimal("7.20"),
            issue_date=date(2025, 1, 1),
            maturity_date=date(2030, 1, 1),
            status=FDRStatus.DRAFT,
        )
        session.add(fdr)
        await session.commit()

    # 2. Upload PDF document with MinIO mocked
    dummy_pdf_bytes = b"%PDF-1.4 Sample AICTE Security Deposit Fixed Deposit Receipt"
    expected_hash = hashlib.sha256(dummy_pdf_bytes).hexdigest()

    with patch.object(
        storage_service,
        "upload_fdr_document",
        return_value="fdrs/200/1710000000_fdr_doc.pdf",
    ):
        files = {
            "file": ("fdr_doc.pdf", dummy_pdf_bytes, "application/pdf")
        }
        upload_res = await client.post("/api/v1/fdr/200/upload-document", files=files)
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        assert upload_data["fdr_id"] == 200
        assert upload_data["document_path"] == "fdrs/200/1710000000_fdr_doc.pdf"
        assert upload_data["document_hash"] == expected_hash
        assert upload_data["file_size_bytes"] == len(dummy_pdf_bytes)

    # 3. Verify audit record was created in DB
    async with session_maker() as session:
        audit_res = await session.execute(
            select(AuditLog).where(AuditLog.action == "FDR_DOCUMENT_UPLOADED")
        )
        audit_log = audit_res.scalar_one()
        assert audit_log is not None
        assert audit_log.user_id == "INSTITUTION_30"

    # 4. Request pre-signed download URL
    with patch.object(
        storage_service,
        "generate_presigned_url",
        return_value="https://minio.local/fdr-documents/fdrs/200/doc.pdf?expires=300",
    ):
        url_res = await client.get("/api/v1/fdr/200/document-url")
        assert url_res.status_code == 200
        url_data = url_res.json()
        assert url_data["fdr_id"] == 200
        assert url_data["expires_in_seconds"] == 300
        assert "minio.local" in url_data["presigned_url"]


@pytest.mark.asyncio
async def test_audit_trail_and_chain_verification_endpoints(client_session):
    client, session_maker = client_session

    # 1. Create a draft and submit it via API (this generates multiple audit logs)
    draft_res = await client.post(
        "/api/v1/fdr/draft",
        json={
            "institution_id": 40,
            "fdr_number": "SBI-AUDIT-1",
            "bank_name": "State Bank of India",
            "ifsc_code": "SBIN0009999",
            "principal_amount": "800000.00",
            "interest_rate": "7.0",
            "issue_date": "2026-01-01",
            "maturity_date": "2031-01-01",
        },
    )
    assert draft_res.status_code == 200
    fdr_id = draft_res.json()["id"]

    submit_res = await client.post(f"/api/v1/fdr/{fdr_id}/submit")
    assert submit_res.status_code == 200

    # 2. Test GET /api/v1/audit/trail
    trail_res = await client.get("/api/v1/audit/trail?limit=10")
    assert trail_res.status_code == 200
    trail_data = trail_res.json()
    assert trail_data["total"] >= 2
    assert len(trail_data["items"]) >= 2
    actions = [item["action"] for item in trail_data["items"]]
    assert "FDR_SUBMITTED" in actions

    # 3. Test GET /api/v1/audit/verify on clean chain
    verify_res = await client.get("/api/v1/audit/verify")
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["valid"] is True
    assert verify_data["broken_at_id"] is None
    assert verify_data["total_records"] >= 2

    # 4. Tamper simulation: directly corrupt an audit log action in the database
    async with session_maker() as session:
        logs_res = await session.execute(select(AuditLog).order_by(AuditLog.id.asc()))
        first_log = logs_res.scalars().first()
        tampered_id = first_log.id
        first_log.action = "TAMPERED_ACTION_MALICIOUS_EDIT"
        session.add(first_log)
        await session.commit()

    # 5. Test GET /api/v1/audit/verify flags broken link and returns broken_at_id
    tampered_verify_res = await client.get("/api/v1/audit/verify")
    assert tampered_verify_res.status_code == 200
    tampered_verify_data = tampered_verify_res.json()
    assert tampered_verify_data["valid"] is False
    assert tampered_verify_data["broken_at_id"] == tampered_id
    assert len(tampered_verify_data["broken_links"]) > 0
