from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse, AuditTrailResponse, AuditVerifyResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/trail", response_model=AuditTrailResponse, status_code=status.HTTP_200_OK)
async def get_audit_trail(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    action: Optional[str] = Query(None, description="Filter by specific action"),
    user_id: Optional[str] = Query(None, description="Filter by user or actor ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated audit trail logs from the immutable hash ledger.
    Ordered by sequential record ID descending.
    """
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)

    # Get total count
    total_res = await db.execute(count_query)
    total_count = total_res.scalar_one() or 0

    # Get paginated slice
    query = query.order_by(AuditLog.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    records = list(result.scalars().all())

    return AuditTrailResponse(
        total=total_count,
        skip=skip,
        limit=limit,
        items=[AuditLogResponse.model_validate(r) for r in records],
    )


@router.get("/verify", response_model=AuditVerifyResponse, status_code=status.HTTP_200_OK)
async def verify_audit_chain_integrity(
    db: AsyncSession = Depends(get_db),
):
    """
    Cryptographic verification endpoint:
    Walks the entire SHA-256 hash chain from genesis block (H_0) to current tip.
    Re-hashes every block H_n = SHA256(H_{n-1} + action + payload_hash + user_id + timestamp),
    verifies previous_hash links, and returns whether the ledger is mathematically intact.
    If corrupted or tampered, flags exact broken_at_id.
    """
    result = await AuditService.verify_chain_integrity(db)

    broken_at_id: Optional[int] = None
    if result["broken_links"]:
        broken_at_id = result["broken_links"][0].get("record_id")

    return AuditVerifyResponse(
        valid=result["is_valid"],
        broken_at_id=broken_at_id,
        total_records=result["total_records"],
        message=result["message"],
        broken_links=result["broken_links"],
        verified_at=result["verified_at"],
    )
