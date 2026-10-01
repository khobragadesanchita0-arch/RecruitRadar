"""
GDPR Article 17 "Right to be Forgotten" Erasure Script.
Permanently expunges a candidate, their encrypted PII, raw files, evidence, and scores.
Usage: python scripts/erase_candidate.py <candidate_id>
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.db.models import (
    Candidate, CandidateProfile, FileRecord, EvidenceItem,
    MatchResult, NoiseReport, ShortlistEntry, InterviewKit
)
from app.core.audit import log_audit_event


async def erase_candidate(candidate_id: str, actor_id: str = "compliance_admin"):
    print(f"Beginning permanent erasure for candidate: {candidate_id}")

    async with AsyncSessionLocal() as session:
        # 1. Verify candidate exists
        stmt = select(Candidate).where(Candidate.id == candidate_id)
        res = await session.execute(stmt)
        cand = res.scalar_one_or_none()
        if not cand:
            print(f"Error: Candidate '{candidate_id}' not found.")
            return False

        workspace_id = cand.workspace_id

        # 2. Delete raw files from local storage
        file_stmt = select(FileRecord).where(FileRecord.candidate_id == candidate_id)
        files = (await session.execute(file_stmt)).scalars().all()
        for f in files:
            file_path = Path(f.storage_key)
            if file_path.exists():
                try:
                    os.remove(file_path)
                    print(f"Deleted physical file: {file_path}")
                except Exception as ex:
                    print(f"Warning: could not delete physical file {file_path}: {ex}")

        # 3. Cascading database deletes
        await session.execute(delete(FileRecord).where(FileRecord.candidate_id == candidate_id))
        await session.execute(delete(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id))
        await session.execute(delete(EvidenceItem).where(EvidenceItem.candidate_id == candidate_id))
        await session.execute(delete(MatchResult).where(MatchResult.candidate_id == candidate_id))
        await session.execute(delete(NoiseReport).where(NoiseReport.candidate_id == candidate_id))
        await session.execute(delete(ShortlistEntry).where(ShortlistEntry.candidate_id == candidate_id))
        await session.execute(delete(InterviewKit).where(InterviewKit.candidate_id == candidate_id))
        await session.execute(delete(Candidate).where(Candidate.id == candidate_id))

        # 4. Record cryptographic compliance audit event
        await log_audit_event(
            session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            action="gdpr_candidate_erased",
            resource_type="candidate",
            resource_id=candidate_id,
            after={"status": "permanently_expunged", "compliance_article": "GDPR_Art_17"},
        )
        await session.commit()
        print(f"Candidate {candidate_id} and all related records successfully expunged from the system.")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/erase_candidate.py <candidate_id>")
        sys.exit(1)
    cid = sys.argv[1]
    asyncio.run(erase_candidate(cid))
