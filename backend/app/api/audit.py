from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import AuditLog
from app.core.authz import Actor
from app.api.deps import require_action

router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.get("")
async def list_audit_logs(
    actor: Actor = Depends(require_action("audit:view")),
    db: AsyncSession = Depends(get_db),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    offset = (page - 1) * page_size
    stmt = (
        select(AuditLog)
        .where(AuditLog.workspace_id == actor.workspace_id)
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

    logs = (await db.execute(stmt)).scalars().all()

    total_stmt = (
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.workspace_id == actor.workspace_id)
    )
    if action:
        total_stmt = total_stmt.where(AuditLog.action == action)
    total = (await db.execute(total_stmt)).scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": [
            {
                "id": log.id,
                "actor_id": log.actor_id,
                "actor_type": log.actor_type,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "before": log.before,
                "after": log.after,
                "request_id": log.request_id,
                "prev_hash": log.prev_hash,
                "hash": log.hash,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }
