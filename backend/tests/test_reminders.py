from datetime import date, datetime, timedelta, timezone
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
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.models.reminder import ReminderAlert, ReminderStatus, ReminderType
from app.services.reminder_service import DEFAULT_OFFSETS, ReminderService
from app.services.storage_service import storage_service


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
async def test_upcoming_maturities_and_idempotency(client_session):
    _, session_maker = client_session
    today = date(2026, 10, 1)

    # 1. Create Institution and Active FDR maturing in 28 days (Oct 29, 2026)
    async with session_maker() as session:
        inst = Institution(
            id=50,
            aicte_permanent_id="AICTE-50",
            name="Apex Institute of Technology",
            state="Karnataka",
            email="registrar@apex.edu",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=300,
            institution_id=50,
            fdr_number="SBI-MAT-300",
            bank_name="State Bank of India",
            ifsc_code="SBIN0007777",
            principal_amount=Decimal("2500000.00"),
            interest_rate=Decimal("7.25"),
            issue_date=date(2021, 10, 29),
            maturity_date=today + timedelta(days=28),  # 28 days remaining
            status=FDRStatus.ACTIVE,
        )
        session.add(fdr)
        await session.commit()

    # 2. Run check_upcoming_maturities
    async with session_maker() as session:
        # Offsets are [90, 60, 30, 15, 7, 1]
        # Days remaining = 28 -> triggers 90, 60, 30 (28 <= 90, 28 <= 60, 28 <= 30)
        alerts = await ReminderService.check_upcoming_maturities(
            session=session,
            reference_date=today,
        )
        await session.commit()

        assert len(alerts) == 3
        triggered_offsets = {a.days_offset for a in alerts}
        assert triggered_offsets == {90, 60, 30}
        for a in alerts:
            assert a.status == ReminderStatus.SENT
            assert a.recipient == "registrar@apex.edu"
            assert "Action: submit a renewal FDR" in a.message

    # 3. IDEMPOTENCY CHECK: Run check_upcoming_maturities AGAIN -> Must produce 0 duplicates
    async with session_maker() as session:
        second_run_alerts = await ReminderService.check_upcoming_maturities(
            session=session,
            reference_date=today,
        )
        await session.commit()
        assert len(second_run_alerts) == 0

        # Verify DB still contains exactly 3 alerts for this FDR
        all_alerts_res = await session.execute(
            select(ReminderAlert).where(ReminderAlert.fdr_id == 300)
        )
        assert len(list(all_alerts_res.scalars().all())) == 3


@pytest.mark.asyncio
async def test_escalation_trigger_within_7_days(client_session):
    _, session_maker = client_session
    today = date(2026, 10, 1)

    # 1. Create alert with due date 5 days away (< 7 days) in SENT status (unacknowledged)
    async with session_maker() as session:
        inst = Institution(
            id=51,
            aicte_permanent_id="AICTE-51",
            name="Bangalore Engineering College",
            state="Karnataka",
            email="registrar@bec.edu",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=301,
            institution_id=51,
            fdr_number="HDFC-MAT-301",
            bank_name="HDFC",
            ifsc_code="HDFC0002222",
            principal_amount=Decimal("1000000.00"),
            interest_rate=Decimal("7.0"),
            issue_date=date(2021, 10, 6),
            maturity_date=today + timedelta(days=5),
            status=FDRStatus.ACTIVE,
        )
        session.add(fdr)
        await session.flush()

        alert = ReminderAlert(
            id=10,
            fdr_id=301,
            institution_id=51,
            reminder_type=ReminderType.UPCOMING_MATURITY,
            days_offset=7,
            due_date=today + timedelta(days=5),
            status=ReminderStatus.SENT,
            message="FDR matures in 5 days.",
            recipient="registrar@bec.edu",
        )
        session.add(alert)
        await session.commit()

    # 2. Run escalation check
    async with session_maker() as session:
        escalated = await ReminderService.check_and_escalate_unacknowledged(
            session=session,
            reference_date=today,
            escalation_threshold_days=7,
        )
        await session.commit()

        assert len(escalated) == 1
        esc_alert = escalated[0]
        assert esc_alert.status == ReminderStatus.ESCALATED
        assert esc_alert.recipient == "regional_officer@aicte-india.org"
        assert "[ESCALATED" in esc_alert.message

        # Verify audit event logged
        audit_res = await session.execute(
            select(AuditLog).where(AuditLog.action == "REMINDER_ALERT_ESCALATED")
        )
        audit_log = audit_res.scalar_one()
        assert audit_log is not None


@pytest.mark.asyncio
async def test_draft_encashment_notice(client_session):
    _, session_maker = client_session

    async with session_maker() as session:
        inst = Institution(
            id=52,
            aicte_permanent_id="AICTE-52",
            name="National College of Tech",
            state="Delhi",
            email="admin@nct.edu",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=302,
            institution_id=52,
            fdr_number="PNB-OVERDUE-302",
            bank_name="Punjab National Bank",
            ifsc_code="PUNB0003333",
            principal_amount=Decimal("1500000.00"),
            interest_rate=Decimal("7.10"),
            issue_date=date(2020, 1, 1),
            maturity_date=date(2025, 1, 1),
            status=FDRStatus.ACTIVE,
        )
        session.add(fdr)
        await session.commit()

    with patch.object(
        storage_service,
        "upload_fdr_document",
        return_value="fdrs/302/Demand_Notice_PNB-OVERDUE-302.pdf",
    ):
        async with session_maker() as session:
            result = await ReminderService.draft_encashment_notice(
                session=session,
                fdr_id=302,
                officer_id="REGIONAL_OFFICER_NORTH",
            )
            await session.commit()

            assert "AICTE/FD/ENCASH" in result["notice_reference"]
            assert result["fdr_status"] == FDRStatus.ENCASHMENT_NOTICE_DRAFTED
            assert result["officer_queue"] == "REGIONAL_OFFICER_NORTH"

            # Check FDR status in DB was updated
            updated_fdr = await session.get(FDR, 302)
            assert updated_fdr.status == FDRStatus.ENCASHMENT_NOTICE_DRAFTED


@pytest.mark.asyncio
async def test_reminder_api_endpoints(client_session):
    client, session_maker = client_session
    today = date.today()

    # Seed alerts in DB
    async with session_maker() as session:
        inst = Institution(
            id=53,
            aicte_permanent_id="AICTE-53",
            name="Chennai Academy",
            state="Tamil Nadu",
            email="registrar@chennai.edu",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=303,
            institution_id=53,
            fdr_number="SBI-API-303",
            bank_name="SBI",
            ifsc_code="SBIN0001111",
            principal_amount=Decimal("500000.00"),
            interest_rate=Decimal("6.5"),
            issue_date=date(2021, 1, 1),
            maturity_date=today + timedelta(days=20),
            status=FDRStatus.ACTIVE,
        )
        session.add(fdr)
        await session.flush()

        # Regular alert
        alert1 = ReminderAlert(
            id=101,
            fdr_id=303,
            institution_id=53,
            reminder_type=ReminderType.UPCOMING_MATURITY,
            days_offset=30,
            due_date=today + timedelta(days=20),
            status=ReminderStatus.SENT,
            message="Alert for institution",
            recipient="registrar@chennai.edu",
        )
        # Escalated alert
        alert2 = ReminderAlert(
            id=102,
            fdr_id=303,
            institution_id=53,
            reminder_type=ReminderType.UPCOMING_MATURITY,
            days_offset=7,
            due_date=today + timedelta(days=2),
            status=ReminderStatus.ESCALATED,
            message="Alert escalated to supervisor",
            recipient="regional_officer@aicte-india.org",
        )
        session.add(alert1)
        session.add(alert2)
        await session.commit()

    # 1. Test GET /api/v1/reminders/active with role=INSTITUTION
    inst_res = await client.get("/api/v1/reminders/active?role=INSTITUTION&institution_id=53")
    assert inst_res.status_code == 200
    inst_data = inst_res.json()
    assert len(inst_data) == 2

    # 2. Test GET /api/v1/reminders/active with role=REGIONAL_OFFICER (only sees ESCALATED)
    officer_res = await client.get("/api/v1/reminders/active?role=REGIONAL_OFFICER")
    assert officer_res.status_code == 200
    officer_data = officer_res.json()
    assert len(officer_data) == 1
    assert officer_data[0]["id"] == 102
    assert officer_data[0]["status"] == "ESCALATED"

    # 3. Test POST /api/v1/reminders/{id}/acknowledge
    ack_res = await client.post(
        "/api/v1/reminders/101/acknowledge",
        json={"actor_id": "REGISTRAR_CHENNAI"},
    )
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["status"] == "ACKNOWLEDGED"
    assert ack_data["acknowledged_by"] == "REGISTRAR_CHENNAI"
    assert ack_data["acknowledged_at"] is not None

    # 4. Test POST /api/v1/reminders/encashment-notice/{fdr_id}
    with patch.object(
        storage_service,
        "upload_fdr_document",
        return_value="fdrs/303/notice.pdf",
    ):
        notice_res = await client.post("/api/v1/reminders/encashment-notice/303")
        assert notice_res.status_code == 200
        notice_data = notice_res.json()
        assert "notice_reference" in notice_data
        assert notice_data["fdr_status"] == "ENCASHMENT_NOTICE_DRAFTED"
