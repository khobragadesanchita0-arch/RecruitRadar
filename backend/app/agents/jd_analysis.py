import secrets
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4
from pydantic import BaseModel
from app.schemas.contracts import Requirement
from app.llm.router import get_llm_provider
from app.taxonomy.normalizer import skill_normalizer

class RawRequirement(BaseModel):
    text: str
    kind: str = "must"  # must, nice
    weight: float = 1.0
    min_months: int | None = None
    skills_mentioned: List[str] = []

class JDAnalysisOutput(BaseModel):
    seniority: str = "Mid-level"
    requirements: List[RawRequirement] = []
    jd_health_flags: List[str] = []

class JDAnalysisAgent:
    def __init__(self):
        self.llm = get_llm_provider()
        prompt_path = Path(__file__).parent / "prompts" / "jd_analysis" / "v1.md"
        self.prompt_template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    async def run(self, jd_text: str) -> Dict[str, Any]:
        nonce = secrets.token_hex(8)
        system_prompt = "You are the JD Analysis Agent for RecruitRadar. Extract structured requirements only."
        user_prompt = f"""Extract key requirements from the job description below.
<untrusted_document id="{nonce}">
{jd_text}
</untrusted_document>"""
        
        extracted = await self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=JDAnalysisOutput,
        )
        
        # Normalize and construct final Requirement objects
        final_reqs: List[Requirement] = []
        for r in extracted.requirements:
            skill_ids = []
            for s_name in r.skills_mentioned:
                norm = await skill_normalizer.normalize(s_name)
                if norm.get("skill_id"):
                    skill_ids.append(norm["skill_id"])
                    
            # Fallback if no skill mentioned, extract from text
            if not skill_ids:
                words = r.text.split()
                for w in words:
                    norm = await skill_normalizer.normalize(w.strip(",.()"))
                    if norm.get("skill_id") and norm["skill_id"] not in skill_ids:
                        skill_ids.append(norm["skill_id"])
                        
            final_reqs.append(Requirement(
                id=uuid4(),
                text=r.text,
                skill_ids=skill_ids,
                kind="must" if r.kind.lower() == "must" else "nice",
                weight=max(0.1, r.weight),
                min_months=r.min_months,
            ))
            
        # Ensure at least 1 requirement exists
        if not final_reqs:
            final_reqs.append(Requirement(
                id=uuid4(),
                text="General technical proficiency",
                skill_ids=[],
                kind="must",
                weight=1.0,
            ))
            
        return {
            "seniority": extracted.seniority,
            "requirements": final_reqs,
            "jd_health_flags": extracted.jd_health_flags,
        }

jd_analysis_agent = JDAnalysisAgent()
