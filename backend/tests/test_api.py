import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test health live endpoint
        live_res = await client.get("/api/health/live")
        assert live_res.status_code == 200
        live_data = live_res.json()
        assert live_data["status"] == "alive"

        # Test main health endpoint (will show degraded or healthy depending on db connection)
        health_res = await client.get("/api/health")
        # In absence of a live postgres container, health status code is 503 degraded, or 200 if connected
        assert health_res.status_code in (200, 503)
        health_data = health_res.json()
        assert "status" in health_data
        assert "service" in health_data
        assert health_data["service"] == "AICTE FinTrust"
        assert "database" in health_data


@pytest.mark.asyncio
async def test_cors_headers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in response.headers
