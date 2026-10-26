from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit import AuditLog
from app.models.clearance import Clearance, ClearanceCell, ClearanceStatus
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.models.provenance import Provenance, ProvenanceSourceType
from app.models.reminder import ReminderAlert, ReminderStatus, ReminderType
from app.services.audit_service import AuditService
from scripts.seed_database import clean_database, seed_data


@pytest.fixture
async def in_memory_session():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_seed_database_execution_and_integrity(in_memory_session: AsyncSession):
    session = in_memory_session

    # Execute seeding
    await seed_data(session)

    # 1. Verify Institutions (3 institutions with specified AICTE IDs and details)
    inst_res = await session.execute(select(Institution).order_by(Institution.id.asc()))
    institutions = inst_res.scalars().all()
    assert len(institutions) == 3

    assert institutions[0].aicte_permanent_id == "1-1002345"
    assert institutions[0].name == "Government College of Engineering"
    assert institutions[0].state == "Maharashtra"
    assert institutions[0].email == "principal@gcoek.ac.in"

    assert institutions[1].aicte_permanent_id == "1-1004567"
    assert institutions[1].name == "Vasantdada Institute of Technology"
    assert institutions[1].state == "Delhi"

    assert institutions[2].aicte_permanent_id == "1-1008910"
    assert institutions[2].name == "National Institute of Advanced Studies"
    assert institutions[2].state == "Karnataka"

    # 2. Verify FDR records (12 total, across DRAFT, ACTIVE, MATURED, RELEASE_REQUESTED)
    fdr_res = await session.execute(select(FDR).order_by(FDR.id.asc()))
    fdrs = fdr_res.scalars().all()
    assert len(fdrs) == 12

    draft_fdrs = [f for f in fdrs if f.status == FDRStatus.DRAFT]
    active_fdrs = [f for f in fdrs if f.status == FDRStatus.ACTIVE]
    matured_fdrs = [f for f in fdrs if f.status == FDRStatus.MATURED]
    rel_req_fdrs = [f for f in fdrs if f.status == FDRStatus.RELEASE_REQUESTED]

    assert len(draft_fdrs) == 3
    assert len(active_fdrs) >= 3
    assert len(matured_fdrs) >= 1
    assert len(rel_req_fdrs) == 3

    # 3. Verify Field Provenance tags
    # For DRAFT FDRs: Provenance must be INSTITUTION_ENTERED
    prov_draft_res = await session.execute(
        select(Provenance).where(Provenance.fdr_id == draft_fdrs[0].id)
    )
    draft_provenances = prov_draft_res.scalars().all()
    assert len(draft_provenances) >= 7
    for p in draft_provenances:
        assert p.source_type == ProvenanceSourceType.INSTITUTION_ENTERED

    # For ACTIVE FDRs: Provenance must be BANK_CONFIRMED
    prov_act_res = await session.execute(
        select(Provenance).where(Provenance.fdr_id == active_fdrs[0].id)
    )
    act_provenances = prov_act_res.scalars().all()
    assert len(act_provenances) >= 7
    for p in act_provenances:
        assert p.source_type == ProvenanceSourceType.BANK_CONFIRMED

    # 4. Verify Release Gate Locks (4 APPROVED, 1 PENDING)
    rel_fdr = rel_req_fdrs[0]
    clearance_res = await session.execute(
        select(Clearance).where(Clearance.fdr_id == rel_fdr.id)
    )
    clearances = clearance_res.scalars().all()
    assert len(clearances) == 5

    approved_cells = [c for c in clearances if c.status == ClearanceStatus.APPROVED]
    pending_cells = [c for c in clearances if c.status == ClearanceStatus.PENDING]
    assert len(approved_cells) == 4
    assert len(pending_cells) == 1
    assert pending_cells[0].cell_name == ClearanceCell.VIGILANCE

    # 5. Verify Reminder Alerts
    alert_res = await session.execute(select(ReminderAlert))
    alerts = alert_res.scalars().all()
    assert len(alerts) >= 2
    maturity_alert = next(a for a in alerts if a.reminder_type == ReminderType.UPCOMING_MATURITY)
    assert maturity_alert.days_offset == 15
    assert maturity_alert.status == ReminderStatus.PENDING

    # 6. Verify Cryptographic SHA-256 Audit Chain Integrity (100% Green)
    audit_report = await AuditService.verify_chain_integrity(session)
    assert audit_report["is_valid"] is True
    assert audit_report["total_records"] >= 20
    assert len(audit_report["broken_links"]) == 0

    # 7. Test Idempotency with Clean and Reseed
    await clean_database(session)
    empty_fdr_res = await session.execute(select(FDR))
    assert len(empty_fdr_res.scalars().all()) == 0

    # Reseed
    await seed_data(session)
    reseed_report = await AuditService.verify_chain_integrity(session)
    assert reseed_report["is_valid"] is True
    assert reseed_report["total_records"] >= 20
