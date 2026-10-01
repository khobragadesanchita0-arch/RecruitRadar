import secrets
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel
from app.schemas.contracts import Requirement, EvidenceItem
from app.llm.router import get_llm_provider
from app.agents.verifier import verify_evidence_items
from app.taxonomy.normalizer import skill_normalizer

class RawEvidence(BaseModel):
    quote: str
    grade: str = "contextual"  # listed, contextual, demonstrated, outcome_backed
    skill_mention: Optional[str] = None
    role_ref: Optional[str] = None
    duration_months: Optional[int] = None
    outcome_text: Optional[str] = None

class EvidenceExtractionOutput(BaseModel):
    evidence_items: List[RawEvidence] = []

class EvidenceAgent:
    def __init__(self):
        self.llm = get_llm_provider()

    async def run(
        self,
        candidate_id: UUID,
        visible_resume_text: str,
        target_requirements: List[Requirement],
        today: date,
    ) -> Tuple[List[EvidenceItem], int]:
        """
        Extracts evidence from resume text for target requirements.
        Verifies all quotes verbatim using span verifier.
        Returns (verified_evidence_items, verifier_rejections).
        """
        nonce = secrets.token_hex(8)
        req_texts = "\n".join([f"- {r.text} (Skills: {r.skill_ids})" for r in target_requirements])
        
        system_prompt = "You are the Evidence Agent for RecruitRadar. Extract VERBATIM quotes with evidence grades."
        user_prompt = f"""Find evidence of experience for these target requirements:
{req_texts}

Grade: listed, contextual, demonstrated, outcome_backed.
<untrusted_document id="{nonce}">
{visible_resume_text}
</untrusted_document>"""
        
        extracted = await self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=EvidenceExtractionOutput,
        )
        
        raw_items: List[EvidenceItem] = []
        for raw in extracted.evidence_items:
            target_skill_id = None
            if raw.skill_mention:
                norm = await skill_normalizer.normalize(raw.skill_mention)
                if norm.get("skill_id"):
                    target_skill_id = UUID(str(norm["skill_id"]))
                    
            if not target_skill_id:
                for r in target_requirements:
                    for s_id in r.skill_ids:
                        target_skill_id = UUID(str(s_id))
                        break
                    if target_skill_id:
                        break
                        
            if not target_skill_id:
                target_skill_id = uuid4()
                
            grade = raw.grade.lower()
            if grade not in ("listed", "contextual", "demonstrated", "outcome_backed"):
                grade = "contextual"
                
            raw_items.append(EvidenceItem(
                id=uuid4(),
                candidate_id=candidate_id,
                skill_id=target_skill_id,
                quote=raw.quote,
                grade=grade,
                role_ref=raw.role_ref,
                duration_months=raw.duration_months or 12,
                last_used=today,
                outcome_text=raw.outcome_text,
                verified=False,
            ))
            
        verified_items, rejections = verify_evidence_items(raw_items, visible_resume_text)
        return verified_items, rejections

evidence_agent = EvidenceAgent()
