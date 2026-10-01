import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import (
    Role, Requirement as RequirementModel, Candidate, CandidateProfile,
    Run, ShortlistEntry as ShortlistEntryModel, MatchResult, NoiseReport,
    EvidenceItem as EvidenceItemModel, InterviewKit, AuditLog
)
from app.core.authz import Actor
from app.core.errors import NotFoundError, ForbiddenError, AppError
from app.api.deps import get_current_actor, require_action
from app.orchestrator.runner import execute_run

router = APIRouter(prefix="/runs", tags=["Runs & Shortlist"])


class CreateRunRequest(BaseModel):
    role_id: str
    params: Dict[str, Any] = {}


class RunResponse(BaseModel):
    id: str
    role_id: str
    state: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@router.post("", response_model=RunResponse)
async def create_run(
    req: CreateRunRequest,
    background_tasks: BackgroundTasks,
    actor: Actor = Depends(require_action("run:create")),
    db: AsyncSession = Depends(get_db),
):
    # Verify role in workspace
    role_stmt = select(Role).where(Role.id == req.role_id, Role.workspace_id == actor.workspace_id)
    role_res = await db.execute(role_stmt)
    role = role_res.scalar_one_or_none()
    if not role:
        raise NotFoundError("Role", req.role_id)

    from app.core.config import settings
    run = Run(
        id=str(uuid.uuid4()),
        workspace_id=actor.workspace_id,
        role_id=req.role_id,
        requested_by=actor.user_id,
        state="CREATED",
        params=req.params,
        plan={},
        budget={"max_usd": settings.run_max_usd},
        scoring_config_version=settings.scoring_config_version,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Fire pipeline in background
    background_tasks.add_task(execute_run, run.id)

    return RunResponse(
        id=run.id,
        role_id=run.role_id,
        state=run.state,
        created_at=run.created_at,
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    actor: Actor = Depends(require_action("run:view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Run).where(Run.id == run_id, Run.workspace_id == actor.workspace_id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise NotFoundError("Run", run_id)
    return RunResponse(
        id=run.id, role_id=run.role_id, state=run.state,
        created_at=run.created_at, started_at=run.started_at, finished_at=run.finished_at
    )


@router.get("/{run_id}/shortlist")
async def get_shortlist(
    run_id: str,
    actor: Actor = Depends(require_action("shortlist:view")),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    # Verify run belongs to workspace
    run_stmt = select(Run).where(Run.id == run_id, Run.workspace_id == actor.workspace_id)
    run_res = await db.execute(run_stmt)
    run = run_res.scalar_one_or_none()
    if not run:
        raise NotFoundError("Run", run_id)

    offset = (page - 1) * page_size
    stmt = (
        select(ShortlistEntryModel, Candidate)
        .join(Candidate, ShortlistEntryModel.candidate_id == Candidate.id)
        .where(ShortlistEntryModel.run_id == run_id)
        .order_by(ShortlistEntryModel.rank)
        .offset(offset)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    rows = res.all()

    total_stmt = select(func.count()).where(ShortlistEntryModel.run_id == run_id)
    total = (await db.execute(total_stmt)).scalar() or 0

    entries = []
    for se, cand in rows:
        # Load matches
        matches_stmt = select(MatchResult).where(
            MatchResult.run_id == run_id,
            MatchResult.candidate_id == se.candidate_id,
        )
        matches_res = await db.execute(matches_stmt)
        matches = matches_res.scalars().all()

        # Load noise flags
        noise_stmt = select(NoiseReport).where(
            NoiseReport.run_id == run_id,
            NoiseReport.candidate_id == se.candidate_id,
        )
        noise_res = await db.execute(noise_stmt)
        noise_report = noise_res.scalar_one_or_none()

        confidence_label = "High" if se.confidence >= 0.75 else ("Med" if se.confidence >= 0.5 else "Low")

        entries.append({
            "rank": se.override_rank or se.rank,
            "candidate_id": se.candidate_id,
            "display_alias": cand.display_alias,
            "fit_score": se.fit_score,
            "confidence": se.confidence,
            "confidence_label": confidence_label,
            "rationale": se.rationale,
            "status": cand.status,
            "gaps": se.gaps or [],
            "matches": [
                {
                    "requirement_id": m.requirement_id,
                    "status": m.status,
                    "strength": round(m.strength, 3),
                    "evidence_ids": m.evidence_ids or [],
                }
                for m in matches
            ],
            "noise_flags": (noise_report.flags if noise_report else []),
            "override_rank": se.override_rank,
            "override_reason": se.override_reason,
        })

    return {
        "run_id": run_id,
        "run_state": run.state,
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": entries,
    }


@router.get("/{run_id}/candidates/{candidate_id}/evidence")
async def get_candidate_evidence(
    run_id: str,
    candidate_id: str,
    actor: Actor = Depends(require_action("candidate:view")),
    db: AsyncSession = Depends(get_db),
):
    # Verify candidate in workspace
    cand_stmt = select(Candidate).where(
        Candidate.id == candidate_id,
        Candidate.workspace_id == actor.workspace_id,
    )
    cand_res = await db.execute(cand_stmt)
    cand = cand_res.scalar_one_or_none()
    if not cand:
        raise NotFoundError("Candidate", candidate_id)

    ev_stmt = select(EvidenceItemModel).where(
        EvidenceItemModel.candidate_id == candidate_id,
        EvidenceItemModel.run_id == run_id,
    )
    ev_res = await db.execute(ev_stmt)
    evidences = ev_res.scalars().all()

    return {
        "candidate_id": candidate_id,
        "display_alias": cand.display_alias,
        "evidence_items": [
            {
                "id": e.id,
                "skill_id": e.skill_id,
                "quote": e.quote,
                "grade": e.grade,
                "role_ref": e.role_ref,
                "duration_months": e.duration_months,
                "last_used": e.last_used,
                "outcome_text": e.outcome_text,
                "verified": e.verified,
                "span_start": e.span_start,
                "span_end": e.span_end,
            }
            for e in evidences
        ],
    }


@router.get("/{run_id}/candidates/{candidate_id}/interview-kit")
async def get_interview_kit(
    run_id: str,
    candidate_id: str,
    actor: Actor = Depends(require_action("interview_kit:view")),
    db: AsyncSession = Depends(get_db),
):
    cand_stmt = select(Candidate).where(
        Candidate.id == candidate_id,
        Candidate.workspace_id == actor.workspace_id,
    )
    cand_res = await db.execute(cand_stmt)
    cand = cand_res.scalar_one_or_none()
    if not cand:
        raise NotFoundError("Candidate", candidate_id)

    kit_stmt = select(InterviewKit).where(
        InterviewKit.run_id == run_id,
        InterviewKit.candidate_id == candidate_id,
    )
    kit_res = await db.execute(kit_stmt)
    kit = kit_res.scalar_one_or_none()
    if not kit:
        raise NotFoundError("InterviewKit", f"{run_id}:{candidate_id}")

    return {
        "candidate_id": candidate_id,
        "display_alias": cand.display_alias,
        "questions": kit.questions,
        "rubric": kit.rubric,
        "created_at": kit.created_at,
    }


class DismissFlagRequest(BaseModel):
    candidate_id: str
    flag_type: str
    reason: str


@router.post("/{run_id}/dismiss-flag")
async def dismiss_noise_flag(
    run_id: str,
    req: DismissFlagRequest,
    actor: Actor = Depends(require_action("shortlist:dismiss_flag")),
    db: AsyncSession = Depends(get_db),
):
    if not req.reason or len(req.reason.strip()) < 10:
        raise AppError("VALIDATION_ERROR", "Dismiss reason must be at least 10 characters", 422)

    noise_stmt = select(NoiseReport).where(
        NoiseReport.run_id == run_id,
        NoiseReport.candidate_id == req.candidate_id,
    )
    noise_res = await db.execute(noise_stmt)
    noise_report = noise_res.scalar_one_or_none()
    if not noise_report:
        raise NotFoundError("NoiseReport", f"{run_id}:{req.candidate_id}")

    flags = noise_report.flags or []
    dismissed = noise_report.dismissed or []
    found = False
    for flag in flags:
        if flag.get("type") == req.flag_type and not flag.get("dismissed"):
            flag["dismissed"] = True
            flag["dismiss_reason"] = req.reason
            dismissed.append({"type": req.flag_type, "reason": req.reason, "by": actor.user_id})
            found = True
            break

    if not found:
        raise AppError("NOT_FOUND", f"Flag {req.flag_type} not found or already dismissed", 404)

    noise_report.flags = flags
    noise_report.dismissed = dismissed

    # Audit log
    from app.core.audit import log_audit_event
    await log_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        action="flag_dismissed",
        resource_type="noise_report",
        resource_id=noise_report.id,
        after={"flag_type": req.flag_type, "reason": req.reason},
    )
    await db.commit()

    # Trigger re-score (simplified: just return updated state)
    return {"message": "Flag dismissed", "flag_type": req.flag_type}


class OverrideRankRequest(BaseModel):
    candidate_id: str
    new_rank: int
    reason: str


@router.post("/{run_id}/override-rank")
async def override_rank(
    run_id: str,
    req: OverrideRankRequest,
    actor: Actor = Depends(require_action("shortlist:reorder")),
    db: AsyncSession = Depends(get_db),
):
    if not req.reason or len(req.reason.strip()) < 10:
        raise AppError("VALIDATION_ERROR", "Override reason must be at least 10 characters", 422)

    se_stmt = select(ShortlistEntryModel).where(
        ShortlistEntryModel.run_id == run_id,
        ShortlistEntryModel.candidate_id == req.candidate_id,
    )
    se_res = await db.execute(se_stmt)
    entry = se_res.scalar_one_or_none()
    if not entry:
        raise NotFoundError("ShortlistEntry", req.candidate_id)

    old_rank = entry.override_rank or entry.rank
    entry.override_rank = req.new_rank
    entry.override_reason = req.reason

    from app.core.audit import log_audit_event
    await log_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        action="rank_overridden",
        resource_type="shortlist_entry",
        resource_id=entry.id,
        before={"rank": old_rank},
        after={"rank": req.new_rank, "reason": req.reason},
    )
    await db.commit()

    return {"message": "Rank overridden", "candidate_id": req.candidate_id, "new_rank": req.new_rank}
