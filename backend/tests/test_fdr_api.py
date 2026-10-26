import asyncio
from datetime import date
from decimal import Decimal
import io
import pytest
from httpx import ASGITransport, AsyncClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.institution import Institution
from app.models.fdr import FDR, FDRStatus


def generate_test_pdf() -> bytes:
    """Generates a synthetic PDF document for upload testing."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "State Bank of India")
    c.drawString(100, 730, "Fixed Deposit Receipt (Security Deposit)")
    c.drawString(100, 710, "FDR No: SBI-FDR-2026-9988")
    c.drawString(100, 690, "IFSC: SBIN0001234")
    c.drawString(100, 670, "Principal Amount: Rs. 10,00,000.00")
    c.drawString(100, 650, "Interest Rate: 7.25% p.a.")
    c.drawString(100, 630, "Issue Date: 15/01/2026")
    c.drawString(100, 610, "Maturity Date: 15/01/2031")
    c.drawString(100, 590, "Lien marked in favour of: AICTE")
    c.save()
    return buffer.getvalue()


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
async def test_create_and_update_draft(client_session):
    client, _ = client_session

    # 1. Create a draft with partial fields
    draft_payload = {
        "institution_id": 1,
        "fdr_number": "SBI-DRAFT-001",
        "bank_name": "State Bank of India",
        "principal_amount": "500000.00",
    }
    response = await client.post("/api/v1/fdr/draft", json=draft_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] is not None
    assert data["status"] == "DRAFT"
    assert data["fdr_number"] == "SBI-DRAFT-001"
    assert data["bank_name"] == "State Bank of India"
    assert len(data["provenance_records"]) >= 3

    # Check field provenance was tagged as INSTITUTION_ENTERED
    bank_prov = next((p for p in data["provenance_records"] if p["field_name"] == "bank_name"), None)
    assert bank_prov is not None
    assert bank_prov["source_type"] == "INSTITUTION_ENTERED"

    created_id = data["id"]

    # 2. Update existing draft with remaining fields
    update_payload = {
        "id": created_id,
        "institution_id": 1,
        "fdr_number": "SBI-DRAFT-001",
        "bank_name": "State Bank of India",
        "ifsc_code": "SBIN0001234",
        "principal_amount": "500000.00",
        "interest_rate": "7.10",
        "issue_date": "2026-01-01",
        "maturity_date": "2031-01-01",
    }
    update_res = await client.post("/api/v1/fdr/draft", json=update_payload)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["ifsc_code"] == "SBIN0001234"
    assert updated_data["maturity_date"] == "2031-01-01"


@pytest.mark.asyncio
async def test_submit_fdr_and_audit_hash(client_session):
    client, _ = client_session

    # 1. Create draft with all required fields
    full_payload = {
        "institution_id": 2,
        "fdr_number": "HDFC-2026-9901",
        "bank_name": "HDFC Bank",
        "ifsc_code": "HDFC0001234",
        "principal_amount": "1000000.00",
        "interest_rate": "7.50",
        "issue_date": "2026-02-01",
        "maturity_date": "2031-02-01",
        "lien_holder": "AICTE",
    }
    res = await client.post("/api/v1/fdr/draft", json=full_payload)
    assert res.status_code == 200
    fdr_id = res.json()["id"]

    # 2. Submit the FDR
    submit_res = await client.post(f"/api/v1/fdr/{fdr_id}/submit")
    assert submit_res.status_code == 200
    submit_data = submit_res.json()
    assert submit_data["fdr"]["status"] == "SUBMITTED"
    assert "audit_hash" in submit_data
    assert len(submit_data["audit_hash"]) == 64

    # 3. Retrieve FDR via GET /api/v1/fdr/{id}
    get_res = await client.get(f"/api/v1/fdr/{fdr_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_get_institution_fdrs(client_session):
    client, _ = client_session

    # Create 2 drafts for institution 5
    await client.post(
        "/api/v1/fdr/draft",
        json={"institution_id": 5, "fdr_number": "INST5-FDR-1", "bank_name": "PNB"},
    )
    await client.post(
        "/api/v1/fdr/draft",
        json={"institution_id": 5, "fdr_number": "INST5-FDR-2", "bank_name": "BOB"},
    )

    # Fetch institution 5 records
    res = await client.get("/api/v1/fdr/institution/5")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 2
    fdr_numbers = [item["fdr_number"] for item in data]
    assert "INST5-FDR-1" in fdr_numbers
    assert "INST5-FDR-2" in fdr_numbers


@pytest.mark.asyncio
async def test_upload_document_triggers_ocr_and_autopopulates_blanks(client_session):
    client, _ = client_session

    # 1. Create a blank draft FDR (fields left empty)
    draft_res = await client.post(
        "/api/v1/fdr/draft",
        json={
            "institution_id": 10,
            "lien_holder": "AICTE",
        },
    )
    assert draft_res.status_code == 200
    fdr_id = draft_res.json()["id"]
    assert draft_res.json()["fdr_number"] is None
    assert draft_res.json()["principal_amount"] is None

    # 2. Upload synthetic FDR PDF
    pdf_bytes = generate_test_pdf()
    upload_res = await client.post(
        f"/api/v1/fdr/{fdr_id}/upload-document",
        files={"file": ("sbi_receipt.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["fdr_id"] == fdr_id
    assert upload_data["document_path"] is not None
    assert upload_data["extracted_fields"] is not None
    assert upload_data["extracted_fields"].get("fdr_number") == "SBI-FDR-2026-9988"

    # 3. Retrieve updated FDR: verify auto-population of blank draft fields
    fdr_res = await client.get(f"/api/v1/fdr/{fdr_id}")
    assert fdr_res.status_code == 200
    fdr_data = fdr_res.json()
    assert fdr_data["fdr_number"] == "SBI-FDR-2026-9988"
    assert fdr_data["bank_name"] == "State Bank of India"
    assert fdr_data["ifsc_code"] == "SBIN0001234"
    assert Decimal(str(fdr_data["principal_amount"])) == Decimal("1000000.00")
    assert fdr_data["maturity_date"] == "2031-01-15"
    assert fdr_data["ocr_status"] in ("PROCESSED", "NEEDS_HUMAN_REVIEW")

    # 4. Verify FieldProvenance records saved with source_type='OCR_EXTRACTED'
    ocr_provs = [p for p in fdr_data["provenance_records"] if p["source_type"] == "OCR_EXTRACTED"]
    assert len(ocr_provs) >= 4
    amt_prov = next(p for p in ocr_provs if p["field_name"] == "principal_amount")
    assert amt_prov["extracted_value"] == "1000000.00"
    assert amt_prov["confidence_score"] >= 0.90


@pytest.mark.asyncio
async def test_get_fdr_provenance_endpoint(client_session):
    client, _ = client_session

    # 1. Create a draft and upload document to generate provenance
    draft_res = await client.post(
        "/api/v1/fdr/draft",
        json={"institution_id": 20, "lien_holder": "AICTE"},
    )
    fdr_id = draft_res.json()["id"]

    pdf_bytes = generate_test_pdf()
    await client.post(
        f"/api/v1/fdr/{fdr_id}/upload-document",
        files={"file": ("deposit_receipt.pdf", pdf_bytes, "application/pdf")},
    )

    # 2. Call GET /api/v1/fdr/{id}/provenance
    prov_res = await client.get(f"/api/v1/fdr/{fdr_id}/provenance")
    assert prov_res.status_code == 200
    prov_data = prov_res.json()

    assert prov_data["fdr_id"] == fdr_id
    assert len(prov_data["provenance_records"]) >= 4
    assert "confidence_flags" in prov_data
    assert "fdr_number" in prov_data["confidence_flags"]

    flag_info = prov_data["confidence_flags"]["fdr_number"]
    assert flag_info["source_type"] == "OCR_EXTRACTED"
    assert flag_info["confidence_score"] >= 0.90
    assert "badge_color" in flag_info
    assert isinstance(prov_data["needs_human_review"], bool)
