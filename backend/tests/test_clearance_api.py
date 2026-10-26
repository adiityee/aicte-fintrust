import asyncio
from datetime import date
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.clearance import ClearanceCell, ClearanceStatus
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution


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
async def test_clearance_gate_full_workflow(client_session):
    client, session_maker = client_session

    # 1. Setup active FDR in the database
    async with session_maker() as session:
        inst = Institution(
            id=10,
            aicte_permanent_id="AICTE-10",
            name="Delhi Tech University",
            state="Delhi",
            email="registrar@dtu.ac.in",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=100,
            institution_id=10,
            fdr_number="SBI-REL-001",
            bank_name="State Bank of India",
            ifsc_code="SBIN0001234",
            principal_amount=Decimal("2000000.00"),
            interest_rate=Decimal("7.0"),
            issue_date=date(2021, 1, 1),
            maturity_date=date(2026, 1, 1),
            status=FDRStatus.ACTIVE,
        )
        session.add(fdr)
        await session.commit()

    # 2. Trigger release request
    req_res = await client.post("/api/v1/clearance/100/request-release")
    assert req_res.status_code == 200
    req_data = req_res.json()
    assert req_data["fdr_status"] == "RELEASE_REQUESTED"
    tasks = req_data["clearances"]
    assert len(tasks) == 5

    cells_in_tasks = {t["cell_name"] for t in tasks}
    expected_cells = {"PGRC", "VIGILANCE", "APPROVAL_BUREAU", "LEGAL", "FINANCE"}
    assert cells_in_tasks == expected_cells

    # Check each cell starts in PENDING status
    for t in tasks:
        assert t["status"] == "PENDING"

    # 3. Action first 4 tasks to APPROVED
    for t in tasks[:4]:
        act_res = await client.put(
            f"/api/v1/clearance/{t['id']}/action",
            json={
                "status": "APPROVED",
                "remarks": f"Cleared by {t['cell_name']} cell",
                "officer_id": f"OFFICER_{t['cell_name']}",
            },
        )
        assert act_res.status_code == 200
        data = act_res.json()
        assert data["task"]["status"] == "APPROVED"
        assert data["fdr_status"] == "RELEASE_REQUESTED"
        assert data["all_cells_approved"] is False

    # 4. Action final (5th) task to APPROVED -> Gate unlocks to CLEARANCES_APPROVED!
    final_task = tasks[4]
    final_res = await client.put(
        f"/api/v1/clearance/{final_task['id']}/action",
        json={
            "status": "APPROVED",
            "remarks": "Final clearance approved",
            "officer_id": f"OFFICER_{final_task['cell_name']}",
        },
    )
    assert final_res.status_code == 200
    final_data = final_res.json()
    assert final_data["task"]["status"] == "APPROVED"
    assert final_data["fdr_status"] == "CLEARANCES_APPROVED"
    assert final_data["all_cells_approved"] is True

    # 5. Verify FDR state updated in GET /api/v1/fdr/{id}
    fdr_get = await client.get("/api/v1/fdr/100")
    assert fdr_get.status_code == 200
    assert fdr_get.json()["status"] == "CLEARANCES_APPROVED"


@pytest.mark.asyncio
async def test_clearance_rejection(client_session):
    client, session_maker = client_session

    # Create active FDR
    async with session_maker() as session:
        inst = Institution(
            id=11,
            aicte_permanent_id="AICTE-11",
            name="Mumbai College of Engg",
            state="Maharashtra",
            email="registrar@mce.ac.in",
        )
        session.add(inst)
        await session.flush()

        fdr = FDR(
            id=101,
            institution_id=11,
            fdr_number="HDFC-REL-002",
            bank_name="HDFC",
            ifsc_code="HDFC0001234",
            principal_amount=Decimal("1000000.00"),
            interest_rate=Decimal("7.0"),
            issue_date=date(2021, 1, 1),
            maturity_date=date(2026, 1, 1),
            status=FDRStatus.ACTIVE,
        )
        session.add(fdr)
        await session.commit()

    # Request release
    req_res = await client.post("/api/v1/clearance/101/request-release")
    assert req_res.status_code == 200
    tasks = req_res.json()["clearances"]

    # Reject first task (e.g. VIGILANCE rejects due to pending inquiry)
    first_task = tasks[0]
    rej_res = await client.put(
        f"/api/v1/clearance/{first_task['id']}/action",
        json={
            "status": "REJECTED",
            "remarks": "Inquiry pending at regional office",
            "officer_id": "VIG_OFFICER_09",
        },
    )
    assert rej_res.status_code == 200
    rej_data = rej_res.json()
    assert rej_data["task"]["status"] == "REJECTED"
    assert rej_data["fdr_status"] == "RELEASE_REQUESTED"
    assert rej_data["all_cells_approved"] is False
