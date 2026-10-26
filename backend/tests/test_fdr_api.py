import asyncio
from datetime import date
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.institution import Institution
from app.models.fdr import FDR, FDRStatus


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
