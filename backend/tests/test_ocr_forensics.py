from datetime import date, datetime, timezone
from decimal import Decimal
import io
import json
from unittest.mock import patch

import pikepdf
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.models.provenance import Provenance, ProvenanceSourceType
from app.schemas.ocr import DuplicateCheckResult, ExtractedFieldItem, TamperIndicatorItem
from app.services.ocr_service import OCRService
from app.services.storage_service import storage_service


def generate_synthetic_fdr_pdf(
    fdr_number: str = "SBI-FDR-2026-9988",
    bank_name: str = "State Bank of India",
    ifsc_code: str = "SBIN0001234",
    principal_amount_str: str = "Rs. 10,00,000.00",
    interest_rate_str: str = "7.25% p.a.",
    issue_date_str: str = "15/01/2026",
    maturity_date_str: str = "15/01/2031",
    lien_holder_str: str = "AICTE",
) -> bytes:
    """Helper to generate a well-structured synthetic FDR PDF for tests."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, f"{bank_name}")
    c.drawString(100, 730, "Fixed Deposit Receipt (Security Deposit)")
    c.drawString(100, 710, f"FDR No: {fdr_number}")
    c.drawString(100, 690, f"IFSC: {ifsc_code}")
    c.drawString(100, 670, f"Principal Amount: {principal_amount_str}")
    c.drawString(100, 650, f"Interest Rate: {interest_rate_str}")
    c.drawString(100, 630, f"Issue Date: {issue_date_str}")
    c.drawString(100, 610, f"Maturity Date: {maturity_date_str}")
    c.drawString(100, 590, f"Lien marked in favour of: {lien_holder_str}")
    c.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Unit Tests: Pass 1 Extraction & Parsing
# ---------------------------------------------------------------------------

def test_extract_clean_fdr_pdf():
    pdf_bytes = generate_synthetic_fdr_pdf()
    extracted, text_len, pages = OCRService.extract_from_pdf(pdf_bytes)

    assert text_len > 100
    assert pages == 1

    # FDR Number
    assert extracted["fdr_number"].extracted_value == "SBI-FDR-2026-9988"
    assert extracted["fdr_number"].confidence_score >= 0.90
    assert extracted["fdr_number"].needs_human_review is False

    # Bank Name
    assert extracted["bank_name"].extracted_value == "State Bank of India"
    assert extracted["bank_name"].confidence_score >= 0.90

    # IFSC Code
    assert extracted["ifsc_code"].extracted_value == "SBIN0001234"
    assert extracted["ifsc_code"].confidence_score >= 0.90

    # Principal Amount
    assert extracted["principal_amount"].extracted_value == "1000000.00"
    assert extracted["principal_amount"].confidence_score >= 0.90

    # Interest Rate
    assert extracted["interest_rate"].extracted_value == "7.25"

    # Dates
    assert extracted["issue_date"].extracted_value == "2026-01-15"
    assert extracted["maturity_date"].extracted_value == "2031-01-15"

    # Lien Holder
    assert extracted["lien_holder"].extracted_value == "AICTE"
    assert extracted["lien_holder"].confidence_score >= 0.95


# ---------------------------------------------------------------------------
# Unit Tests: Forensics Tamper Indicators
# ---------------------------------------------------------------------------

def test_detect_tamper_multiple_incremental_revisions():
    clean_bytes = generate_synthetic_fdr_pdf()
    # Simulate post-generation append edit with extra %%EOF marker
    tampered_bytes = clean_bytes + b"\n% Tampered revision trailer\n%%EOF\n"

    indicators = OCRService.detect_tamper_indicators(tampered_bytes)
    codes = [i.indicator_code for i in indicators]
    assert "MULTIPLE_INCREMENTAL_REVISIONS" in codes

    rev_indicator = next(i for i in indicators if i.indicator_code == "MULTIPLE_INCREMENTAL_REVISIONS")
    assert rev_indicator.severity == "HIGH"
    assert rev_indicator.details["eof_count"] >= 2


def test_detect_tamper_suspicious_creator_metadata():
    clean_bytes = generate_synthetic_fdr_pdf()
    buf = io.BytesIO()
    with pikepdf.open(io.BytesIO(clean_bytes)) as pdf:
        pdf.docinfo["/Creator"] = "Canva Online Editor"
        pdf.save(buf)

    canva_bytes = buf.getvalue()
    indicators = OCRService.detect_tamper_indicators(canva_bytes)
    codes = [i.indicator_code for i in indicators]
    assert "SUSPICIOUS_CREATOR_METADATA" in codes

    creator_ind = next(i for i in indicators if i.indicator_code == "SUSPICIOUS_CREATOR_METADATA")
    assert creator_ind.severity == "HIGH"
    assert creator_ind.details["tool"] == "canva"


def test_detect_tamper_modified_post_issuance():
    clean_bytes = generate_synthetic_fdr_pdf()
    buf = io.BytesIO()
    with pikepdf.open(io.BytesIO(clean_bytes)) as pdf:
        pdf.docinfo["/CreationDate"] = "D:20260101000000"
        pdf.docinfo["/ModDate"] = "D:20260601000000"
        pdf.save(buf)

    mod_bytes = buf.getvalue()
    indicators = OCRService.detect_tamper_indicators(mod_bytes, issue_date=date(2026, 1, 15))
    codes = [i.indicator_code for i in indicators]
    assert "MODIFIED_POST_ISSUANCE" in codes


# ---------------------------------------------------------------------------
# Unit Tests: Pass 2 Side-by-Side Discrepancy Matching
# ---------------------------------------------------------------------------

def test_pass2_side_by_side_discrepancy_amount_mismatch():
    # Institution declared ₹10 Lakhs, but document says ₹1 Lakh
    sample_fdr = FDR(
        id=501,
        institution_id=1,
        fdr_number="SBI-FDR-2026-9988",
        bank_name="State Bank of India",
        ifsc_code="SBIN0001234",
        principal_amount=Decimal("1000000.00"),  # ₹10,00,000 declared
        maturity_date=date(2031, 1, 15),
        lien_holder="AICTE",
    )

    extracted_fields = {
        "principal_amount": ExtractedFieldItem(
            field_name="principal_amount",
            extracted_value="100000.00",  # ₹1,00,000 on document!
            confidence_score=0.96,
            source_snippet="Principal Amount: Rs. 1,00,000.00",
            needs_human_review=False,
        ),
        "fdr_number": ExtractedFieldItem(
            field_name="fdr_number",
            extracted_value="SBI-FDR-2026-9988",
            confidence_score=0.96,
        ),
        "bank_name": ExtractedFieldItem(
            field_name="bank_name",
            extracted_value="State Bank of India",
            confidence_score=0.96,
        ),
        "ifsc_code": ExtractedFieldItem(
            field_name="ifsc_code",
            extracted_value="SBIN0001234",
            confidence_score=0.98,
        ),
        "maturity_date": ExtractedFieldItem(
            field_name="maturity_date",
            extracted_value="2031-01-15",
            confidence_score=0.95,
        ),
        "lien_holder": ExtractedFieldItem(
            field_name="lien_holder",
            extracted_value="AICTE",
            confidence_score=0.98,
        ),
    }

    report = OCRService.compare_discrepancies(
        fdr=sample_fdr,
        extracted_fields=extracted_fields,
        tamper_indicators=[],
        duplicate_check=DuplicateCheckResult(),
    )

    assert report.has_discrepancies is True
    assert report.critical_count == 1
    assert report.discrepancy_count == 1
    assert "principal_amount" in report.fields

    amt_comp = report.fields["principal_amount"]
    assert amt_comp.is_mismatch is True
    assert amt_comp.severity == "CRITICAL"
    assert amt_comp.badge_color == "red"
    assert amt_comp.submitted_value == "1000000.00"
    assert amt_comp.extracted_value == "100000.00"
    assert "Scrutiny Officer Review Required" in report.recommended_action


# ---------------------------------------------------------------------------
# Integration Tests: In-Memory DB & API Endpoints
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
async def test_duplicate_detection_hash_and_cross_institution_reuse(client_session):
    _, session_maker = client_session

    async with session_maker() as session:
        # Create 2 institutions
        inst1 = Institution(id=1, aicte_permanent_id="AICTE-001", name="Inst 1", state="Delhi", email="i1@aicte.gov.in")
        inst2 = Institution(id=2, aicte_permanent_id="AICTE-002", name="Inst 2", state="Mumbai", email="i2@aicte.gov.in")
        session.add_all([inst1, inst2])
        await session.flush()

        # FDR 1 belonging to Inst 1
        fdr1 = FDR(
            id=101,
            institution_id=1,
            fdr_number="SBI-CROSS-9999",
            bank_name="State Bank of India",
            document_hash="shared_sha256_hash_value",
            principal_amount=Decimal("500000.00"),
        )
        session.add(fdr1)
        await session.flush()

        # Inst 2 uploads FDR with identical SHA-256
        res_dup_hash = await OCRService.check_duplicates(
            session=session,
            fdr_id=102,
            file_hash="shared_sha256_hash_value",
            fdr_number="NEW-NUM",
            bank_name="Other Bank",
            institution_id=2,
        )
        assert res_dup_hash.is_duplicate_hash is True
        assert res_dup_hash.duplicate_fdr_id == 101

        # Inst 2 attempts to register same FDR number + bank
        res_cross_reuse = await OCRService.check_duplicates(
            session=session,
            fdr_id=103,
            file_hash="unique_hash_xyz",
            fdr_number="SBI-CROSS-9999",
            bank_name="State Bank of India",
            institution_id=2,
        )
        assert res_cross_reuse.is_cross_institution_reuse is True
        assert res_cross_reuse.reused_fdr_id == 101
        assert res_cross_reuse.reused_institution_id == 1


@pytest.mark.asyncio
async def test_officer_verify_field_workflow(client_session):
    _, session_maker = client_session

    async with session_maker() as session:
        inst = Institution(id=10, aicte_permanent_id="AICTE-010", name="Tech College", state="Karnataka", email="tc@aicte.gov.in")
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=601,
            institution_id=10,
            fdr_number="HDFC-9911",
            bank_name="HDFC Bank",
            principal_amount=Decimal("500000.00"),
            status=FDRStatus.UNDER_SCRUTINY,
        )
        session.add(fdr)
        await session.flush()

        # Officer accepts corrected amount ₹10,00,000.00
        prov, audit_entry = await OCRService.verify_field(
            session=session,
            fdr=fdr,
            field_name="principal_amount",
            accepted_value="1000000.00",
            officer_id="SCRUTINY_OFFICER_01",
            remarks="Verified against original bank passbook copy",
        )

        assert prov.source_type == ProvenanceSourceType.OFFICER_VERIFIED
        assert prov.confidence_score == 1.0
        assert prov.extracted_value == "1000000.00"
        assert fdr.principal_amount == Decimal("1000000.00")
        assert audit_entry.action == "FDR_FIELD_VERIFIED"
        assert audit_entry.user_id == "SCRUTINY_OFFICER_01"


@pytest.mark.asyncio
async def test_ocr_api_process_and_discrepancy_endpoints(client_session):
    client, session_maker = client_session

    pdf_bytes = generate_synthetic_fdr_pdf(
        fdr_number="SBI-FDR-2026-9988",
        bank_name="State Bank of India",
        principal_amount_str="Rs. 10,00,000.00",
    )

    # 1. Create a draft FDR
    draft_res = await client.post(
        "/api/v1/fdr/draft",
        json={
            "institution_id": 99,
            "fdr_number": "SBI-FDR-2026-9988",
            "bank_name": "State Bank of India",
            "principal_amount": "1000000.00",
            "lien_holder": "AICTE",
        },
    )
    assert draft_res.status_code == 200
    fdr_data = draft_res.json()
    fdr_id = fdr_data["id"]

    # Mock MinIO storage upload and download
    with patch.object(storage_service, "upload_fdr_document", return_value=f"fdrs/{fdr_id}/test_fdr.pdf"), \
         patch.object(storage_service, "download_fdr_document", return_value=pdf_bytes):

        # 2. Call POST /api/v1/ocr/{fdr_id}/process with uploaded PDF
        process_res = await client.post(
            f"/api/v1/ocr/{fdr_id}/process",
            files={"file": ("test_fdr.pdf", pdf_bytes, "application/pdf")},
        )
        assert process_res.status_code == 200
        proc_data = process_res.json()
        assert proc_data["fdr_id"] == fdr_id
        assert proc_data["ocr_status"] == "PROCESSED"
        assert proc_data["extracted_fields"]["fdr_number"]["extracted_value"] == "SBI-FDR-2026-9988"
        assert proc_data["extracted_fields"]["principal_amount"]["extracted_value"] == "1000000.00"

        # 3. Call GET /api/v1/ocr/{fdr_id}/discrepancies
        disc_res = await client.get(f"/api/v1/ocr/{fdr_id}/discrepancies")
        assert disc_res.status_code == 200
        disc_data = disc_res.json()
        assert disc_data["fdr_id"] == fdr_id
        assert disc_data["has_discrepancies"] is False
        assert disc_data["fields"]["principal_amount"]["badge_color"] == "green"
        assert disc_data["fields"]["fdr_number"]["badge_color"] == "green"

        # 4. Scrutiny Officer verifies a field via POST /api/v1/ocr/{fdr_id}/verify-field
        verify_res = await client.post(
            f"/api/v1/ocr/{fdr_id}/verify-field",
            json={
                "field_name": "principal_amount",
                "accepted_value": "1000000.00",
                "officer_id": "OFFICER_PATIL",
                "remarks": "Confirmed with bank statement",
            },
        )
        assert verify_res.status_code == 200
        v_data = verify_res.json()
        assert v_data["provenance_source"] == "OFFICER_VERIFIED"
        assert v_data["verified_value"] == "1000000.00"
        assert "audit_hash" in v_data

        # 5. Call POST /api/v1/fdr/{fdr_id}/validate-ocr
        val_res = await client.post(f"/api/v1/fdr/{fdr_id}/validate-ocr")
        assert val_res.status_code == 200
        val_data = val_res.json()
        assert val_data["fdr_id"] == fdr_id
        assert "All fields match" in val_data["recommended_action"]
