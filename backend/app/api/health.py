import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine

router = APIRouter()


async def check_db_connection() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


@router.get("", tags=["Health"])
@router.get("/", tags=["Health"])
async def get_health_status():
    """
    Health check endpoint for FinTrust API.
    Checks database connection and system readiness.
    """
    db_status = "unknown"
    is_healthy = True

    try:
        await asyncio.wait_for(check_db_connection(), timeout=1.5)
        db_status = "connected"
    except Exception as exc:
        db_status = f"unreachable ({type(exc).__name__})"
        is_healthy = False

    response_data = {
        "status": "healthy" if is_healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=response_data)


@router.get("/live", tags=["Health"])
async def liveness_probe():
    """
    Kubernetes / Docker liveness probe: returns 200 OK if server process is running.
    """
    return {
        "status": "alive",
        "service": settings.PROJECT_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
