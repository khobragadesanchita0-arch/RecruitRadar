import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Run, Approval, AuditLog
from app.core.authz import Actor
from app.core.errors import NotFoundError, AppError
from app.api.deps import require_action

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class CreateApprovalRequest(BaseModel):
    run_id: str
    shortlist_snapshot: List[str]  # candidate_ids in rank order
    note: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    note: Optional[str] = None


@router.post("")
async def request_approval(
    req: CreateApprovalRequest,
    actor: Actor = Depends(require_action("approval:create")),
    db: AsyncSession = Depends(get_db),
):
    run_stmt = select(Run).where(Run.id == req.run_id, Run.workspace_id == actor.workspace_id)
    run_res = await db.execute(run_stmt)
    run = run_res.scalar_one_or_none()
    if not run:
        raise NotFoundError("Run", req.run_id)

    # Check for existing pending approval
    existing_stmt = select(Approval).where(
        Approval.run_id == req.run_id,
        Approval.status == "pending",
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        return {"approval_id": existing.id, "state": "pending", "message": "Approval already pending"}

    payload_data = {"shortlist": req.shortlist_snapshot}
    payload_hash = hashlib.sha256(json.dumps(payload_data, sort_keys=True).encode("utf-8")).hexdigest()

    approval = Approval(
        id=str(uuid.uuid4()),
        workspace_id=actor.workspace_id,
        run_id=req.run_id,
        action_type="shortlist_approval",
        risk="HIGH",
        payload=payload_data,
        payload_hash=payload_hash,
        status="pending",
        requested_by=actor.user_id,
        note=req.note,
    )
    db.add(approval)

    from app.core.audit import log_audit_event
    await log_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        action="approval_requested",
        resource_type="approval",
        resource_id=approval.id,
        after={"run_id": req.run_id, "payload_hash": payload_hash},
    )
    await db.commit()
    await db.refresh(approval)

    return {
        "approval_id": approval.id,
        "state": approval.status,
        "payload_hash": approval.payload_hash,
        "requested_at": approval.created_at,
    }


@router.get("")
async def list_approvals(
    actor: Actor = Depends(require_action("approval:view")),
    db: AsyncSession = Depends(get_db),
    state: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    offset = (page - 1) * page_size
    stmt = select(Approval).where(Approval.workspace_id == actor.workspace_id)
    if state:
        stmt = stmt.where(Approval.status == state.lower())
    stmt = stmt.order_by(Approval.created_at.desc()).offset(offset).limit(page_size)
    approvals = (await db.execute(stmt)).scalars().all()

    total_stmt = select(func.count()).select_from(Approval).where(
        Approval.workspace_id == actor.workspace_id
    )
    if state:
        total_stmt = total_stmt.where(Approval.status == state.lower())
    total = (await db.execute(total_stmt)).scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "approvals": [
            {
                "id": a.id,
                "run_id": a.run_id,
                "state": a.status,
                "action_type": a.action_type,
                "risk": a.risk,
                "requested_by": a.requested_by,
                "decided_by": a.approver_id,
                "note": a.note,
                "created_at": a.created_at,
                "decided_at": a.decided_at,
            }
            for a in approvals
        ],
    }


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    actor: Actor = Depends(require_action("approval:view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Approval).where(
        Approval.id == approval_id,
        Approval.workspace_id == actor.workspace_id,
    )
    approval = (await db.execute(stmt)).scalar_one_or_none()
    if not approval:
        raise NotFoundError("Approval", approval_id)

    return {
        "id": approval.id,
        "run_id": approval.run_id,
        "state": approval.status,
        "shortlist_snapshot": approval.payload.get("shortlist", []),
        "payload_hash": approval.payload_hash,
        "requested_by": approval.requested_by,
        "decided_by": approval.approver_id,
        "note": approval.note,
        "created_at": approval.created_at,
        "decided_at": approval.decided_at,
    }


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    req: ApprovalDecisionRequest,
    actor: Actor = Depends(require_action("approval:decide")),
    db: AsyncSession = Depends(get_db),
):
    decision_clean = req.decision.lower()
    if decision_clean not in ("approved", "rejected"):
        raise AppError("VALIDATION_ERROR", "decision must be 'approved' or 'rejected'", 422)

    stmt = select(Approval).where(
        Approval.id == approval_id,
        Approval.workspace_id == actor.workspace_id,
    )
    approval = (await db.execute(stmt)).scalar_one_or_none()
    if not approval:
        raise NotFoundError("Approval", approval_id)
    if approval.status != "pending":
        raise AppError("INVALID_STATE", f"Approval is already {approval.status}", 409)

    # Prevent self-approval
    if approval.requested_by == actor.user_id and not actor.is_admin:
        raise AppError("SELF_APPROVAL_FORBIDDEN", "You cannot approve your own request", 403)

    approval.status = decision_clean
    approval.approver_id = actor.user_id
    approval.decided_at = datetime.now(timezone.utc)
    if req.note:
        approval.note = req.note

    from app.core.audit import log_audit_event
    await log_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        action=f"approval_{decision_clean}",
        resource_type="approval",
        resource_id=approval.id,
        after={"decision": decision_clean, "note": req.note},
    )
    await db.commit()

    return {
        "approval_id": approval.id,
        "state": approval.status,
        "decided_by": approval.approver_id,
        "decided_at": approval.decided_at,
    }
