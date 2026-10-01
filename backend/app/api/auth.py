import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Cookie
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import User, Workspace, WorkspaceMember, RefreshToken
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_token
)
from app.core.errors import AppError, UnauthorizedError, ConflictError
from app.core.audit import log_audit_event
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    workspace_name: Optional[str] = "Default Workspace"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes
    workspace_id: str
    user: dict[str, Any]

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    res = await db.execute(select(User).where(User.email == req.email))
    if res.scalar_one_or_none():
        raise ConflictError("User with this email already exists")
        
    workspace = Workspace(name=req.workspace_name)
    db.add(workspace)
    await db.flush()
    
    user = User(
        email=req.email,
        name=req.name,
        password_hash=hash_password(req.password),
        status="active"
    )
    db.add(user)
    await db.flush()
    
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner"
    )
    db.add(member)
    
    # Create tokens
    access_token = create_access_token({"sub": user.id, "email": user.email})
    raw_refresh = create_refresh_token({"sub": user.id})
    token_hash = hashlib.sha256(raw_refresh.encode('utf-8')).hexdigest()
    
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(refresh_record)
    
    await log_audit_event(
        db,
        workspace_id=workspace.id,
        actor_id=user.id,
        action="user_registered",
        resource_type="user",
        resource_id=user.id,
        after={"email": user.email, "name": user.name},
    )
    
    await db.commit()
    
    # Set refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        samesite="lax",
        secure=False,  # dev mode; prod: True
        max_age=7 * 24 * 3600
    )
    
    return TokenResponse(
        access_token=access_token,
        workspace_id=workspace.id,
        user={"id": user.id, "email": user.email, "name": user.name, "role": "owner"}
    )

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == req.email))
    user = res.scalar_one_or_none()
    
    if not user:
        raise UnauthorizedError("Invalid email or password")
        
    # Check lockout
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise AppError("ACCOUNT_LOCKED", "Account temporarily locked due to too many failed attempts. Try again later.", 403)
        
    if not verify_password(req.password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = now + timedelta(minutes=15)
        await db.commit()
        raise UnauthorizedError("Invalid email or password")
        
    # Reset failed logins
    user.failed_logins = 0
    user.locked_until = None
    
    # Get user's primary workspace
    res_mem = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
    member = res_mem.scalars().first()
    workspace_id = member.workspace_id if member else ""
    user_role = member.role if member else "viewer"
    
    access_token = create_access_token({"sub": user.id, "email": user.email})
    raw_refresh = create_refresh_token({"sub": user.id})
    token_hash = hashlib.sha256(raw_refresh.encode('utf-8')).hexdigest()
    
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=now + timedelta(days=7),
    )
    db.add(refresh_record)
    
    if workspace_id:
        await log_audit_event(
            db,
            workspace_id=workspace_id,
            actor_id=user.id,
            action="user_login",
            resource_type="user",
            resource_id=user.id
        )
        
    await db.commit()
    
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 24 * 3600
    )
    
    return TokenResponse(
        access_token=access_token,
        workspace_id=workspace_id,
        user={"id": user.id, "email": user.email, "name": user.name, "role": user_role}
    )

@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: Optional[str] = Cookie(None)
):
    token = refresh_token or request.headers.get("X-Refresh-Token")
    if not token:
        raise UnauthorizedError("Missing refresh token")
        
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid or expired refresh token")
        
    user_id = payload.get("sub")
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    stmt = (
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None)
        )
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record or record.expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError("Refresh token revoked or expired")
        
    # Rotate token
    record.revoked_at = datetime.now(timezone.utc)
    
    new_access_token = create_access_token({"sub": user_id})
    new_raw_refresh = create_refresh_token({"sub": user_id})
    new_token_hash = hashlib.sha256(new_raw_refresh.encode('utf-8')).hexdigest()
    
    new_record = RefreshToken(
        user_id=user_id,
        token_hash=new_token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(new_record)
    await db.commit()
    
    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 24 * 3600
    )
    
    return {"access_token": new_access_token, "token_type": "bearer", "expires_in": 900}

@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    refresh_token: Optional[str] = Cookie(None)
):
    token = refresh_token or request.headers.get("X-Refresh-Token")
    if token:
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if record:
            record.revoked_at = datetime.now(timezone.utc)
            await db.commit()
            
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(WorkspaceMember, Workspace)
        .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
    )
    res = await db.execute(stmt)
    workspaces = []
    for member, ws in res.all():
        workspaces.append({
            "workspace_id": ws.id,
            "workspace_name": ws.name,
            "role": member.role,
            "retention_days": ws.retention_days,
            "blind_mode_default": ws.blind_mode_default,
        })
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "status": user.status,
        "workspaces": workspaces,
    }
