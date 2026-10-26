from datetime import date, datetime, timezone
from decimal import Decimal
import pytest

from app.models.institution import Institution
from app.models.fdr import FDR, FDRStatus
from app.models.provenance import Provenance, ProvenanceSourceType
from app.models.clearance import Clearance, ClearanceCell, ClearanceStatus
from app.models.audit import AuditLog


def test_institution_model_attributes():
    inst = Institution(
        id=1,
        aicte_permanent_id="1-1234567890",
        name="Indian Institute of Technology Excellence",
        state="Maharashtra",
        email="contact@iite.ac.in",
    )
    assert inst.id == 1
    assert inst.aicte_permanent_id == "1-1234567890"
    assert inst.name == "Indian Institute of Technology Excellence"
    assert inst.state == "Maharashtra"
    assert inst.email == "contact@iite.ac.in"


def test_fdr_model_attributes_and_enum():
    # Verify all enum values required by specification
    expected_statuses = {
        "DRAFT",
        "SUBMITTED",
        "UNDER_SCRUTINY",
        "QUERY_RAISED",
        "BANK_VERIFICATION_PENDING",
        "BANK_VERIFIED",
        "ACTIVE",
        "MATURED",
        "RENEWED",
        "RELEASE_REQUESTED",
        "CLEARANCES_APPROVED",
        "RELEASED",
        "ENCASHMENT_NOTICE_DRAFTED",
    }
    actual_statuses = {status.value for status in FDRStatus}
    assert expected_statuses == actual_statuses

    fdr = FDR(
        id=101,
        institution_id=1,
        fdr_number="SBI-FDR-2026-9988",
        bank_name="State Bank of India",
        ifsc_code="SBIN0001234",
        principal_amount=Decimal("1000000.00"),
        interest_rate=Decimal("7.25"),
        issue_date=date(2026, 1, 15),
        maturity_date=date(2031, 1, 15),
        lien_holder="AICTE",
        status=FDRStatus.DRAFT,
    )
    assert fdr.fdr_number == "SBI-FDR-2026-9988"
    assert fdr.principal_amount == Decimal("1000000.00")
    assert fdr.interest_rate == Decimal("7.25")
    assert fdr.lien_holder == "AICTE"
    assert fdr.status == FDRStatus.DRAFT


def test_provenance_model_and_enum():
    expected_sources = {
        "INSTITUTION_ENTERED",
        "OCR_EXTRACTED",
        "OFFICER_VERIFIED",
        "BANK_CONFIRMED",
    }
    actual_sources = {s.value for s in ProvenanceSourceType}
    assert expected_sources == actual_sources

    now = datetime.now(timezone.utc)
    prov = Provenance(
        id=1,
        fdr_id=101,
        field_name="principal_amount",
        source_type=ProvenanceSourceType.OCR_EXTRACTED,
        confidence_score=0.96,
        extracted_value="1000000.00",
        updated_at=now,
    )
    assert prov.fdr_id == 101
    assert prov.field_name == "principal_amount"
    assert prov.source_type == ProvenanceSourceType.OCR_EXTRACTED
    assert prov.confidence_score == 0.96


def test_clearance_model_and_enums():
    expected_cells = {
        "PGRC",
        "VIGILANCE",
        "APPROVAL_BUREAU",
        "LEGAL",
        "FINANCE",
    }
    actual_cells = {c.value for c in ClearanceCell}
    assert expected_cells == actual_cells

    expected_statuses = {"PENDING", "APPROVED", "REJECTED"}
    actual_statuses = {s.value for s in ClearanceStatus}
    assert expected_statuses == actual_statuses

    clearance = Clearance(
        id=1,
        fdr_id=101,
        cell_name=ClearanceCell.VIGILANCE,
        status=ClearanceStatus.PENDING,
        remarks="Awaiting clearance confirmation",
        officer_id="OFFICER_VIG_01",
    )
    assert clearance.cell_name == ClearanceCell.VIGILANCE
    assert clearance.status == ClearanceStatus.PENDING
    assert clearance.officer_id == "OFFICER_VIG_01"


def test_audit_model_attributes():
    now = datetime.now(timezone.utc)
    audit = AuditLog(
        id=1,
        previous_hash="0" * 64,
        current_hash="a" * 64,
        action="FDR_CREATED",
        payload_hash="b" * 64,
        user_id="ADMIN_01",
        timestamp=now,
    )
    assert audit.previous_hash == "0" * 64
    assert audit.action == "FDR_CREATED"
    assert audit.user_id == "ADMIN_01"
