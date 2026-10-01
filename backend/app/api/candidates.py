import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import Candidate, CandidateProfile, Role
from app.core.authz import Actor
from app.core.errors import NotFoundError, AppError
from app.api.deps import require_action
from app.storage.service import intake_pipeline
from app.core.audit import log_audit_event

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.post("", status_code=201)
async def upload_candidate(
    role_id: str = Form(...),
    file: UploadFile = File(...),
    actor: Actor = Depends(require_action("candidate:create")),
    db: AsyncSession = Depends(get_db),
):
    # Verify role
    role_stmt = select(Role).where(Role.id == role_id, Role.workspace_id == actor.workspace_id)
    role_res = await db.execute(role_stmt)
    role = role_res.scalar_one_or_none()
    if not role:
        raise NotFoundError("Role", role_id)

    # Read file bytes
    content = await file.read()
    if len(content) == 0:
        raise AppError("VALIDATION_ERROR", "Uploaded file is empty", 422)
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise AppError("FILE_TOO_LARGE", "File exceeds 10MB limit", 413)

    # Run intake pipeline
    try:
        result = await intake_pipeline(
            file_bytes=content,
            filename=file.filename or "resume.pdf",
            content_type=file.content_type or "application/octet-stream",
            workspace_id=actor.workspace_id,
        )
    except Exception as e:
        raise AppError("INTAKE_ERROR", f"Failed to process file: {e}", 422)

    if result.get("quarantined"):
        raise AppError("FILE_QUARANTINED", "File failed security scan", 422)

    if result.get("injection_detected"):
        raise AppError("PROMPT_INJECTION", "Resume contains prohibited injection content", 422)

    # Create candidate record
    display_alias = f"Candidate-{str(uuid.uuid4())[:8].upper()}"
    candidate_id = str(uuid.uuid4())

    pii_data = result.get("pii_blob")
    if isinstance(pii_data, str):
        pii_bytes = pii_data.encode("utf-8")
    elif isinstance(pii_data, bytes):
        pii_bytes = pii_data
    else:
        pii_bytes = None

    candidate = Candidate(
        id=candidate_id,
        workspace_id=actor.workspace_id,
        role_id=role_id,
        display_alias=display_alias,
        pii_encrypted=pii_bytes,
        status="uploaded",
    )
    db.add(candidate)

    # Create file record
    from app.db.models import FileRecord
    file_record = FileRecord(
        workspace_id=actor.workspace_id,
        candidate_id=candidate_id,
        storage_key=f"uploads/{candidate_id}/{file.filename or 'resume.pdf'}",
        filename=file.filename or "resume.pdf",
        mime=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        sha256=result.get("raw_hash", "0" * 64),
        scan_status="clean",
        parse_status="parsed",
    )
    db.add(file_record)

    # Create profile
    profile = CandidateProfile(
        candidate_id=candidate_id,
        parsed=result.get("parsed", {}),
        analysis_text=result.get("analysis_text", ""),
        hidden_text_flags=result.get("hidden_text_flags", []),
        parse_confidence=result.get("parse_confidence", 0.8),
        parser_version="1.0.0",
    )
    db.add(profile)

    await log_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        action="candidate_uploaded",
        resource_type="candidate",
        resource_id=candidate_id,
        after={
            "filename": file.filename,
            "role_id": role_id,
            "display_alias": display_alias,
        },
    )
    await db.commit()

    return {
        "candidate_id": candidate_id,
        "display_alias": display_alias,
        "status": "uploaded",
        "warnings": result.get("warnings", []),
        "hidden_text_flags_count": len(result.get("hidden_text_flags", [])),
        "injection_flags_count": len(result.get("injection_flags", [])),
    }


@router.get("")
async def list_candidates(
    actor: Actor = Depends(require_action("candidate:view")),
    db: AsyncSession = Depends(get_db),
    role_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    offset = (page - 1) * page_size
    stmt = (
        select(Candidate)
        .where(
            Candidate.workspace_id == actor.workspace_id,
            Candidate.deleted_at.is_(None),
        )
        .order_by(Candidate.created_at.desc())
    )
    if role_id:
        stmt = stmt.where(Candidate.role_id == role_id)
    if status_filter:
        stmt = stmt.where(Candidate.status == status_filter)
    stmt = stmt.offset(offset).limit(page_size)

    res = await db.execute(stmt)
    candidates = res.scalars().all()

    total_stmt = select(func.count()).select_from(Candidate).where(
        Candidate.workspace_id == actor.workspace_id,
        Candidate.deleted_at.is_(None),
    )
    if role_id:
        total_stmt = total_stmt.where(Candidate.role_id == role_id)
    if status_filter:
        total_stmt = total_stmt.where(Candidate.status == status_filter)
    total = (await db.execute(total_stmt)).scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "candidates": [
            {
                "id": c.id,
                "display_alias": c.display_alias,
                "role_id": c.role_id,
                "status": c.status,
                "created_at": c.created_at,
            }
            for c in candidates
        ],
    }


@router.get("/{candidate_id}")
async def get_candidate(
    candidate_id: str,
    actor: Actor = Depends(require_action("candidate:view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Candidate, CandidateProfile).join(
        CandidateProfile, CandidateProfile.candidate_id == Candidate.id, isouter=True
    ).where(
        Candidate.id == candidate_id,
        Candidate.workspace_id == actor.workspace_id,
        Candidate.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise NotFoundError("Candidate", candidate_id)

    cand, profile = row

    return {
        "id": cand.id,
        "display_alias": cand.display_alias,
        "role_id": cand.role_id,
        "status": cand.status,
        "created_at": cand.created_at,
        "profile": {
            "parser_version": profile.parser_version if profile else None,
            "parse_confidence": profile.parse_confidence if profile else None,
            "hidden_text_flags_count": len(profile.hidden_text_flags or []) if profile else 0,
        } if profile else None,
    }


@router.delete("/{candidate_id}", status_code=204)
async def delete_candidate(
    candidate_id: str,
    actor: Actor = Depends(require_action("candidate:delete")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Candidate).where(
        Candidate.id == candidate_id,
        Candidate.workspace_id == actor.workspace_id,
    )
    res = await db.execute(stmt)
    cand = res.scalar_one_or_none()
    if not cand or cand.deleted_at:
        raise NotFoundError("Candidate", candidate_id)

    cand.deleted_at = datetime.now(timezone.utc)
    await log_audit_event(
        db, workspace_id=actor.workspace_id,
        actor_id=actor.user_id, action="candidate_deleted",
        resource_type="candidate", resource_id=candidate_id,
    )
    await db.commit()
