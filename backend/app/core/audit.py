"""
Structured audit logging — writes immutable entries to the audit_log table.
Features cryptographic chaining (SHA-256) per workspace.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog


async def log_audit_event(
    db: AsyncSession,
    workspace_id: str,
    actor_id: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    actor_type: str = "user",
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Write an immutable audit log entry with SHA-256 hash chaining."""
    # Find prev_hash in workspace
    stmt = (
        select(AuditLog.hash)
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    prev_hash = res.scalar_one_or_none() or ("0" * 64)

    now = datetime.now(timezone.utc)
    entry_id = str(uuid.uuid4())
    before_dict = before or {}
    after_dict = after or {}
    if ip_address and "ip_address" not in after_dict:
        after_dict["ip_address"] = ip_address

    # Compute SHA-256 hash chaining
    payload = f"{prev_hash}:{workspace_id}:{actor_id}:{action}:{resource_type}:{resource_id}:{json.dumps(before_dict, sort_keys=True)}:{json.dumps(after_dict, sort_keys=True)}:{now.isoformat()}"
    current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    entry = AuditLog(
        id=entry_id,
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before_dict,
        after=after_dict,
        request_id=request_id,
        prev_hash=prev_hash,
        hash=current_hash,
        created_at=now,
    )
    db.add(entry)
    return entry
