from typing import AsyncGenerator, Optional
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import User, WorkspaceMember, Workspace
from app.core.security import decode_token
from app.core.authz import Actor
from app.core.errors import AppError, ForbiddenError


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(code="UNAUTHORIZED", detail=detail, status_code=401)


security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise UnauthorizedError("Missing authentication token")

    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token subject")

    stmt = select(User).where(User.id == user_id, User.status == "active")
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User not found or inactive")

    return user


async def get_current_actor(
    user: User = Depends(get_current_user),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    db: AsyncSession = Depends(get_db),
) -> Actor:
    # If workspace_id header provided, check membership in that workspace
    if x_workspace_id:
        stmt = (
            select(WorkspaceMember, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.workspace_id == x_workspace_id,
            )
        )
        result = await db.execute(stmt)
        row = result.first()
        if row:
            member, workspace = row
            return Actor(
                user_id=user.id,
                workspace_id=member.workspace_id,
                tenant_id=workspace.id,
                role=member.role,
                is_admin=(member.role in ("admin", "owner")),
            )

    # Fallback to user's first workspace
    stmt = (
        select(WorkspaceMember, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.created_at)
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise ForbiddenError("access any workspace")

    member, workspace = row
    return Actor(
        user_id=user.id,
        workspace_id=member.workspace_id,
        tenant_id=workspace.id,
        role=member.role,
        is_admin=(member.role in ("admin", "owner")),
    )


def require_action(action: str):
    async def dependency(actor: Actor = Depends(get_current_actor)) -> Actor:
        actor.require(action)
        return actor
    return dependency
