from app.api.v1.audit import router as audit_router
from app.api.v1.clearance import router as clearance_router
from app.api.v1.fdr import router as fdr_router
from app.api.v1.ocr import router as ocr_router
from app.api.v1.reminders import router as reminders_router
from app.api.v1.verify import router as verify_router

__all__ = ["fdr_router", "clearance_router", "audit_router", "reminders_router", "verify_router", "ocr_router"]
