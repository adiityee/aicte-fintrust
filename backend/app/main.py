import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.health import router as health_router
from app.api.v1.audit import router as audit_router
from app.api.v1.clearance import router as clearance_router
from app.api.v1.fdr import router as fdr_router
from app.core.config import settings
from app.core.database import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup table preparation and graceful engine disposal on shutdown.
    """
    # Startup actions
    try:
        # Create database tables if they do not exist (timeout to avoid blocking in offline mode)
        await asyncio.wait_for(init_db(), timeout=1.5)
    except Exception as e:
        print(f"[FinTrust Warning] Could not connect to database on startup: {e}")

    yield

    # Shutdown actions
    try:
        await engine.dispose()
    except Exception:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AICTE FinTrust Security Deposit & FDR Management Portal - Core API",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(health_router, prefix="/api/health", tags=["Health"])
app.include_router(fdr_router, prefix="/api/v1/fdr", tags=["FDR Management"])
app.include_router(clearance_router, prefix="/api/v1/clearance", tags=["Clearance Gate"])
app.include_router(audit_router, prefix="/api/v1/audit", tags=["Audit Ledger"])


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root path to interactive Swagger documentation."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_check": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
