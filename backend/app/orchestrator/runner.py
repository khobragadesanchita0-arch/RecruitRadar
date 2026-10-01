"""
Full pipeline orchestrator — runs all 8 agents for a given run_id.
Idempotent: uses idempotency_key = run_id:step:candidate_id.
"""
import asyncio
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.models import (
    Run, Role, Candidate, CandidateProfile, Requirement as RequirementModel,
    EvidenceItem as EvidenceItemModel, MatchResult, NoiseReport,
    ShortlistEntry as ShortlistEntryModel, InterviewKit, TaskStep,
)
from app.db.session import AsyncSessionLocal
from app.schemas.contracts import (
    Requirement, EvidenceItem, NoiseFlag, RequirementMatch, ShortlistEntry
)
from app.agents.jd_analysis import jd_analysis_agent
from app.agents.evidence import evidence_agent
from app.agents.matcher import matcher_agent
from app.agents.shortlist import shortlist_agent
from app.agents.interview import interview_agent
from app.noise.rules import run_noise_detection
from app.core.config import settings
from app.core.logging import app_logger


async def _get_or_skip_step(db: AsyncSession, idempotency_key: str) -> Optional[Any]:
    """Returns existing output if step already completed (idempotency)."""
    stmt = select(TaskStep).where(TaskStep.idempotency_key == idempotency_key)
    res = await db.execute(stmt)
    step = res.scalar_one_or_none()
    if step and step.state == "DONE":
        return step.output_ref
    return None


async def _mark_step_done(db: AsyncSession, task_id: str, idempotency_key: str, seq: int, agent: str, output_ref: Any):
    stmt = select(TaskStep).where(TaskStep.idempotency_key == idempotency_key)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        existing.state = "DONE"
        existing.output_ref = output_ref
    else:
        step = TaskStep(
            task_id=task_id,
            seq=seq,
            agent=agent,
            idempotency_key=idempotency_key,
            state="DONE",
            output_ref=output_ref,
        )
        db.add(step)
    await db.commit()


async def execute_run(run_id: str):
    """
    Main pipeline executor for a Run.
    Runs agents in sequence, checkpointing each step for idempotency.
    """
    app_logger.info(f"Starting pipeline execution for run_id={run_id}")

    async with AsyncSessionLocal() as db:
        # Load run
        run_stmt = select(Run).where(Run.id == run_id)
        run_res = await db.execute(run_stmt)
        run = run_res.scalar_one_or_none()
        if not run:
            app_logger.error(f"Run not found: {run_id}")
            return

        # Load role + JD
        role_stmt = select(Role).where(Role.id == run.role_id)
        role_res = await db.execute(role_stmt)
        role = role_res.scalar_one_or_none()
        if not role:
            await _set_run_state(db, run, "FAILED", error="Role not found")
            return

        # Update run state
        run.state = "EXECUTING"
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        today = date.today()
        task_id = str(uuid.uuid4())

        try:
            # ──────────────────────────────────────────────────────
            # STEP 1: JD Analysis (idempotent)
            # ──────────────────────────────────────────────────────
            jd_ikey = f"{run_id}:jd_analysis"
            jd_cached = await _get_or_skip_step(db, jd_ikey)

            if jd_cached:
                requirements_data = jd_cached.get("requirements", [])
            else:
                jd_result = await jd_analysis_agent.run(role.jd_text)
                requirements_data = [r.model_dump() for r in jd_result["requirements"]]

                # Persist requirements to DB
                for req_dict in requirements_data:
                    existing_stmt = select(RequirementModel).where(
                        RequirementModel.role_id == role.id,
                        RequirementModel.text == req_dict["text"],
                    )
                    existing_res = await db.execute(existing_stmt)
                    if not existing_res.scalar_one_or_none():
                        req_model = RequirementModel(
                            id=str(req_dict["id"]),
                            role_id=role.id,
                            jd_version=role.jd_version,
                            text=req_dict["text"],
                            skill_ids=req_dict["skill_ids"],
                            kind=req_dict["kind"],
                            weight=req_dict["weight"],
                            min_months=req_dict.get("min_months"),
                        )
                        db.add(req_model)
                await db.commit()
                await _mark_step_done(db, task_id, jd_ikey, 1, "jd_analysis", {"requirements": requirements_data})

            # Re-load requirements from DB for this role
            req_stmt = select(RequirementModel).where(RequirementModel.role_id == role.id)
            req_res = await db.execute(req_stmt)
            db_reqs = req_res.scalars().all()

            requirements: List[Requirement] = [
                Requirement(
                    id=r.id,
                    text=r.text,
                    skill_ids=r.skill_ids or [],
                    kind=r.kind,
                    weight=r.weight,
                    min_months=r.min_months,
                )
                for r in db_reqs
            ]

            # ──────────────────────────────────────────────────────
            # STEP 2..N: Per-candidate pipeline
            # ──────────────────────────────────────────────────────
            cand_stmt = select(Candidate, CandidateProfile).join(
                CandidateProfile, CandidateProfile.candidate_id == Candidate.id, isouter=True
            ).where(Candidate.role_id == role.id, Candidate.deleted_at.is_(None))
            cand_res = await db.execute(cand_stmt)
            candidate_rows = cand_res.all()

            candidates_scored: List[Any] = []
            evidences_by_candidate: Dict[str, List[EvidenceItem]] = {}

            for candidate, profile in candidate_rows:
                cid = candidate.id
                if not profile or not profile.analysis_text:
                    continue

                # EVIDENCE extraction (idempotent)
                ev_ikey = f"{run_id}:evidence:{cid}"
                ev_cached = await _get_or_skip_step(db, ev_ikey)

                if ev_cached:
                    evidences = [EvidenceItem(**e) for e in ev_cached.get("evidence_items", [])]
                    rejections = ev_cached.get("rejections", 0)
                else:
                    evidences, rejections = await evidence_agent.run(
                        candidate_id=uuid.UUID(cid),
                        visible_resume_text=profile.analysis_text,
                        target_requirements=requirements,
                        today=today,
                    )

                    # Persist evidence to DB
                    for ev in evidences:
                        existing_ev = await db.execute(
                            select(EvidenceItemModel).where(
                                EvidenceItemModel.candidate_id == cid,
                                EvidenceItemModel.run_id == run_id,
                                EvidenceItemModel.skill_id == str(ev.skill_id),
                                EvidenceItemModel.quote == ev.quote,
                            )
                        )
                        if not existing_ev.scalar_one_or_none():
                            db.add(EvidenceItemModel(
                                id=str(ev.id),
                                candidate_id=cid,
                                run_id=run_id,
                                skill_id=str(ev.skill_id),
                                quote=ev.quote,
                                span_start=ev.span_start,
                                span_end=ev.span_end,
                                grade=ev.grade,
                                role_ref=ev.role_ref,
                                duration_months=ev.duration_months,
                                last_used=ev.last_used,
                                outcome_text=ev.outcome_text,
                                verified=ev.verified,
                            ))
                    await db.commit()

                    cached_ev = {
                        "evidence_items": [e.model_dump(mode="json") for e in evidences],
                        "rejections": rejections,
                    }
                    await _mark_step_done(db, task_id, ev_ikey, 2, "evidence", cached_ev)

                evidences_by_candidate[cid] = evidences

                # NOISE detection (idempotent)
                noise_ikey = f"{run_id}:noise:{cid}"
                noise_cached = await _get_or_skip_step(db, noise_ikey)

                if noise_cached:
                    noise_flags = [NoiseFlag(**f) for f in noise_cached.get("flags", [])]
                else:
                    sections = profile.parsed.get("sections", {}) if profile.parsed else {}
                    skills_listed = sum(
                        1 for e in evidences if e.grade == "listed"
                    )
                    skills_with_ctx = sum(
                        1 for e in evidences if e.grade != "listed"
                    )
                    noise_flags = run_noise_detection(
                        resume_text=profile.analysis_text,
                        jd_text=role.jd_text,
                        section_texts=sections,
                        skills_listed_count=skills_listed,
                        skills_with_context_count=skills_with_ctx,
                        hidden_text_items=profile.hidden_text_flags or [],
                        evidences=evidences,
                        skills_map={},
                    )
                    # Combine with injection flags found during parsing
                    for hf in (profile.hidden_text_flags or []):
                        if hf.get("type") == "HIDDEN_TEXT":
                            noise_flags.append(NoiseFlag(
                                type="HIDDEN_TEXT",
                                severity="MED",
                                detail=hf.get("reason", "Hidden text detected"),
                                metrics=hf,
                            ))

                    # Persist noise report
                    existing_nr = await db.execute(
                        select(NoiseReport).where(
                            NoiseReport.run_id == run_id,
                            NoiseReport.candidate_id == cid
                        )
                    )
                    if not existing_nr.scalar_one_or_none():
                        db.add(NoiseReport(
                            run_id=run_id,
                            candidate_id=cid,
                            flags=[f.model_dump() for f in noise_flags],
                        ))
                    await db.commit()
                    await _mark_step_done(db, task_id, noise_ikey, 3, "noise",
                                          {"flags": [f.model_dump() for f in noise_flags]})

                # MATCHING / SCORING (idempotent)
                match_ikey = f"{run_id}:match:{cid}"
                match_cached = await _get_or_skip_step(db, match_ikey)

                if match_cached:
                    fit_score = match_cached.get("fit_score", 0)
                    confidence = match_cached.get("confidence", 0.0)
                    matches_list = [RequirementMatch(**m) for m in match_cached.get("matches", [])]
                    gaps = match_cached.get("gaps", [])
                    rationale = match_cached.get("rationale", "")
                else:
                    verifier_pass_rate = (
                        len([e for e in evidences if e.verified]) / max(1, len(evidences))
                    )
                    fit_score, confidence, matches_list, gaps, rationale = matcher_agent.run(
                        candidate_id=uuid.UUID(cid),
                        requirements=requirements,
                        evidences=evidences,
                        noise_flags=noise_flags,
                        today=today,
                        parse_confidence=profile.parse_confidence,
                        verifier_pass_rate=verifier_pass_rate,
                    )

                    # Persist match results
                    for m in matches_list:
                        existing_mr = await db.execute(
                            select(MatchResult).where(
                                MatchResult.run_id == run_id,
                                MatchResult.candidate_id == cid,
                                MatchResult.requirement_id == str(m.requirement_id),
                            )
                        )
                        if not existing_mr.scalar_one_or_none():
                            db.add(MatchResult(
                                run_id=run_id,
                                candidate_id=cid,
                                requirement_id=str(m.requirement_id),
                                status=m.status,
                                strength=m.strength,
                                evidence_ids=[str(eid) for eid in m.evidence_ids],
                            ))
                    await db.commit()

                    cached_match = {
                        "fit_score": fit_score,
                        "confidence": confidence,
                        "matches": [m.model_dump(mode="json") for m in matches_list],
                        "gaps": gaps,
                        "rationale": rationale,
                    }
                    await _mark_step_done(db, task_id, match_ikey, 4, "matcher", cached_match)

                candidates_scored.append((
                    uuid.UUID(cid), fit_score, confidence,
                    matches_list, noise_flags, gaps, rationale
                ))

            # ──────────────────────────────────────────────────────
            # STEP: Shortlist
            # ──────────────────────────────────────────────────────
            must_req_ids = {r.id for r in requirements if r.kind == "must"}
            ev_by_uuid = {uuid.UUID(k): v for k, v in evidences_by_candidate.items()}

            shortlist_entries = shortlist_agent.run(
                candidates_scored_data=candidates_scored,
                evidences_by_candidate=ev_by_uuid,
                must_req_ids=must_req_ids,
            )

            # Persist shortlist
            for entry in shortlist_entries:
                existing_se = await db.execute(
                    select(ShortlistEntryModel).where(
                        ShortlistEntryModel.run_id == run_id,
                        ShortlistEntryModel.candidate_id == str(entry.candidate_id),
                    )
                )
                se_obj = existing_se.scalar_one_or_none()
                if se_obj:
                    se_obj.rank = entry.rank
                    se_obj.fit_score = entry.fit_score
                    se_obj.confidence = entry.confidence
                    se_obj.rationale = entry.rationale
                    se_obj.gaps = entry.gaps
                else:
                    db.add(ShortlistEntryModel(
                        run_id=run_id,
                        candidate_id=str(entry.candidate_id),
                        rank=entry.rank,
                        fit_score=entry.fit_score,
                        confidence=entry.confidence,
                        rationale=entry.rationale,
                        gaps=entry.gaps,
                    ))
            await db.commit()

            # ──────────────────────────────────────────────────────
            # STEP: Interview kits for top candidates
            # ──────────────────────────────────────────────────────
            top_candidates = shortlist_entries[:min(10, len(shortlist_entries))]
            for entry in top_candidates:
                cid_str = str(entry.candidate_id)
                kit_ikey = f"{run_id}:interview:{cid_str}"
                kit_cached = await _get_or_skip_step(db, kit_ikey)
                if not kit_cached:
                    cand_matches = next(
                        (m for (cid, *_) in candidates_scored if str(cid) == cid_str),
                        None
                    )
                    cand_evidences = evidences_by_candidate.get(cid_str, [])
                    kit = await interview_agent.run(
                        candidate_id=entry.candidate_id,
                        gaps=entry.gaps,
                        matches=[],
                        noise_flags=entry.noise_flags,
                        verified_evidences=cand_evidences,
                    )
                    existing_kit = await db.execute(
                        select(InterviewKit).where(
                            InterviewKit.run_id == run_id,
                            InterviewKit.candidate_id == cid_str,
                        )
                    )
                    if not existing_kit.scalar_one_or_none():
                        db.add(InterviewKit(
                            run_id=run_id,
                            candidate_id=cid_str,
                            questions=kit["questions"],
                            rubric=kit.get("rubric", {}),
                        ))
                    await db.commit()
                    await _mark_step_done(db, task_id, kit_ikey, 5, "interview", kit)

            # Mark run complete
            run.state = "COMPLETED"
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            app_logger.info(f"Run {run_id} completed successfully. {len(shortlist_entries)} candidates ranked.")

        except Exception as e:
            app_logger.error(f"Pipeline error for run {run_id}: {e}", exc_info=True)
            async with AsyncSessionLocal() as db2:
                run_stmt2 = select(Run).where(Run.id == run_id)
                run_res2 = await db2.execute(run_stmt2)
                run2 = run_res2.scalar_one_or_none()
                if run2:
                    run2.state = "FAILED"
                    run2.finished_at = datetime.now(timezone.utc)
                    await db2.commit()


async def _set_run_state(db: AsyncSession, run: Run, state: str, error: Optional[str] = None):
    run.state = state
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()
