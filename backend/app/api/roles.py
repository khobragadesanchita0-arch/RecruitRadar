import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Form, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import Role, Requirement as RequirementModel, Candidate, CandidateProfile, Run
from app.core.authz import Actor
from app.core.errors import NotFoundError, AppError
from app.api.deps import require_action
from app.core.audit import log_audit_event

router = APIRouter(prefix="/roles", tags=["Roles"])


class CreateRoleRequest(BaseModel):
    title: str
    jd_text: str
    jd_version: int = 1


class UpdateRoleRequest(BaseModel):
    title: Optional[str] = None
    jd_text: Optional[str] = None
    jd_version: Optional[int] = None


class RoleResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    jd_version: int
    created_at: datetime
    updated_at: Optional[datetime] = None


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    req: CreateRoleRequest,
    actor: Actor = Depends(require_action("role:create")),
    db: AsyncSession = Depends(get_db),
):
    if not req.title.strip():
        raise AppError("VALIDATION_ERROR", "Role title cannot be empty", 422)
    if len(req.jd_text.strip()) < 50:
        raise AppError("VALIDATION_ERROR", "JD text must be at least 50 characters", 422)

    role = Role(
        id=str(uuid.uuid4()),
        workspace_id=actor.workspace_id,
        title=req.title.strip(),
        jd_text=req.jd_text,
        jd_version=req.jd_version,
    )
    db.add(role)
    await log_audit_event(
        db, workspace_id=actor.workspace_id,
        actor_id=actor.user_id, action="role_created",
        resource_type="role", resource_id=role.id,
        after={"title": role.title, "jd_version": role.jd_version},
    )
    await db.commit()
    await db.refresh(role)

    return RoleResponse(
        id=role.id,
        workspace_id=role.workspace_id,
        title=role.title,
        jd_version=role.jd_version,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("")
async def list_roles(
    actor: Actor = Depends(require_action("role:view")),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    offset = (page - 1) * page_size
    stmt = (
        select(Role)
        .where(Role.workspace_id == actor.workspace_id, Role.deleted_at.is_(None))
        .order_by(Role.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    roles = res.scalars().all()

    total_stmt = select(func.count()).select_from(Role).where(
        Role.workspace_id == actor.workspace_id, Role.deleted_at.is_(None)
    )
    total = (await db.execute(total_stmt)).scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "roles": [
            {
                "id": r.id,
                "title": r.title,
                "jd_version": r.jd_version,
                "created_at": r.created_at,
            }
            for r in roles
        ],
    }


@router.get("/{role_id}")
async def get_role(
    role_id: str,
    actor: Actor = Depends(require_action("role:view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Role).where(Role.id == role_id, Role.workspace_id == actor.workspace_id)
    res = await db.execute(stmt)
    role = res.scalar_one_or_none()
    if not role or role.deleted_at:
        raise NotFoundError("Role", role_id)

    # Load requirements
    req_stmt = select(RequirementModel).where(RequirementModel.role_id == role_id)
    req_res = await db.execute(req_stmt)
    requirements = req_res.scalars().all()

    return {
        "id": role.id,
        "workspace_id": role.workspace_id,
        "title": role.title,
        "jd_text": role.jd_text,
        "jd_version": role.jd_version,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
        "requirements": [
            {
                "id": r.id,
                "text": r.text,
                "kind": r.kind,
                "weight": r.weight,
                "min_months": r.min_months,
                "skill_ids": r.skill_ids or [],
            }
            for r in requirements
        ],
    }


@router.patch("/{role_id}")
async def update_role(
    role_id: str,
    req: UpdateRoleRequest,
    actor: Actor = Depends(require_action("role:edit")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Role).where(Role.id == role_id, Role.workspace_id == actor.workspace_id)
    res = await db.execute(stmt)
    role = res.scalar_one_or_none()
    if not role or role.deleted_at:
        raise NotFoundError("Role", role_id)

    before = {"title": role.title, "jd_version": role.jd_version}
    if req.title:
        role.title = req.title.strip()
    if req.jd_text:
        role.jd_text = req.jd_text
    if req.jd_version:
        role.jd_version = req.jd_version
    role.updated_at = datetime.now(timezone.utc)

    await log_audit_event(
        db, workspace_id=actor.workspace_id,
        actor_id=actor.user_id, action="role_updated",
        resource_type="role", resource_id=role.id,
        before=before,
        after={"title": role.title, "jd_version": role.jd_version},
    )
    await db.commit()

    return {"id": role.id, "title": role.title, "jd_version": role.jd_version}


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: str,
    actor: Actor = Depends(require_action("role:delete")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Role).where(Role.id == role_id, Role.workspace_id == actor.workspace_id)
    res = await db.execute(stmt)
    role = res.scalar_one_or_none()
    if not role or role.deleted_at:
        raise NotFoundError("Role", role_id)

    role.deleted_at = datetime.now(timezone.utc)
    await log_audit_event(
        db, workspace_id=actor.workspace_id,
        actor_id=actor.user_id, action="role_deleted",
        resource_type="role", resource_id=role.id,
    )
    await db.commit()
