import uuid
from typing import Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import FileRecord, Candidate, CandidateProfile, Role
from app.core.authz import Actor
from app.core.errors import NotFoundError, AppError
from app.api.deps import get_current_actor, require_action
from app.storage.service import storage_service, process_and_parse_file

router = APIRouter(prefix="/files", tags=["Files"])

class UploadUrlRequest(BaseModel):
    filename: str
    mime: str
    size_bytes: int
    role_id: str

class UploadUrlResponse(BaseModel):
    file_id: str
    storage_key: str
    upload_url: str

@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    req: UploadUrlRequest,
    actor: Actor = Depends(require_action("file:upload")),
    db: AsyncSession = Depends(get_db),
):
    # Verify role exists in workspace
    r_stmt = select(Role).where(Role.id == req.role_id, Role.workspace_id == actor.workspace_id)
    r_res = await db.execute(r_stmt)
    if not r_res.scalar_one_or_none():
        raise NotFoundError("Role", req.role_id)
        
    file_id = str(uuid.uuid4())
    storage_key = f"{file_id}_{req.filename}"
    upload_url = f"/api/v1/files/{file_id}/upload-direct"
    
    # Pre-register file record
    record = FileRecord(
        id=file_id,
        workspace_id=actor.workspace_id,
        storage_key=storage_key,
        filename=req.filename,
        mime=req.mime,
        size_bytes=req.size_bytes,
        sha256="",
        scan_status="pending",
        parse_status="pending",
    )
    db.add(record)
    await db.commit()
    
    return UploadUrlResponse(
        file_id=file_id,
        storage_key=storage_key,
        upload_url=upload_url,
    )

@router.post("/upload")
async def upload_direct_file(
    role_id: str,
    file: UploadFile = File(...),
    actor: Actor = Depends(require_action("file:upload")),
    db: AsyncSession = Depends(get_db),
):
    r_stmt = select(Role).where(Role.id == role_id, Role.workspace_id == actor.workspace_id)
    r_res = await db.execute(r_stmt)
    role = r_res.scalar_one_or_none()
    if not role:
        raise NotFoundError("Role", role_id)
        
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE", "File size exceeds 10MB limit", 413)
        
    key, sha256 = storage_service.save_quarantine(content, file.filename or "resume.pdf")
    
    # Process and parse file
    intake = process_and_parse_file(content, file.filename or "resume.pdf", file.content_type or "application/pdf")
    
    file_id = str(uuid.uuid4())
    record = FileRecord(
        id=file_id,
        workspace_id=actor.workspace_id,
        storage_key=key,
        filename=file.filename or "resume",
        mime=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        sha256=sha256,
        scan_status=intake["scan_status"],
        parse_status=intake["parse_status"],
    )
    db.add(record)
    await db.flush()
    
    cand_record = None
    if intake["scan_status"] == "clean":
        storage_service.promote_to_clean(key)
        
        # Count existing candidates in role for display alias
        c_count_res = await db.execute(select(Candidate).where(Candidate.role_id == role_id))
        count = len(c_count_res.scalars().all())
        alias = f"Candidate #{chr(65 + (count // 99))}{count % 99 + 1:02d}"
        
        cand = Candidate(
            workspace_id=actor.workspace_id,
            role_id=role_id,
            display_alias=alias,
            pii_encrypted=intake.get("encrypted_pii"),
            status="new",
            dedupe_hash=sha256,
        )
        db.add(cand)
        await db.flush()
        
        record.candidate_id = cand.id
        
        # Save profile
        profile = CandidateProfile(
            candidate_id=cand.id,
            parsed={
                "sections": intake.get("sections", {}),
                "extracted_pii": intake.get("extracted_pii", {}),
            },
            analysis_text=intake.get("analysis_text", ""),
            hidden_text_flags=intake.get("hidden_text_items", []),
            parse_confidence=intake.get("parse_confidence", 1.0),
        )
        db.add(profile)
        cand_record = {
            "id": cand.id,
            "display_alias": cand.display_alias,
            "parse_confidence": intake.get("parse_confidence", 1.0),
        }
        
    await db.commit()
    await db.refresh(record)
    
    return {
        "file_id": record.id,
        "filename": record.filename,
        "scan_status": record.scan_status,
        "parse_status": record.parse_status,
        "candidate": cand_record,
        "error": intake.get("error"),
    }

@router.get("/{id}")
async def get_file(
    id: str,
    actor: Actor = Depends(require_action("file:view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FileRecord).where(FileRecord.id == id, FileRecord.workspace_id == actor.workspace_id)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise NotFoundError("File", id)
        
    return {
        "id": record.id,
        "filename": record.filename,
        "mime": record.mime,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
        "scan_status": record.scan_status,
        "parse_status": record.parse_status,
        "candidate_id": record.candidate_id,
        "created_at": record.created_at,
    }
