from app.api.v1.audit import router as audit_router
from app.api.v1.clearance import router as clearance_router
from app.api.v1.fdr import router as fdr_router

__all__ = ["fdr_router", "clearance_router", "audit_router"]
