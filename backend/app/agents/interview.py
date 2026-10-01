import secrets
from typing import Any, Dict, List
from uuid import UUID
from pydantic import BaseModel
from app.llm.router import get_llm_provider
from app.redaction.protected import filter_protected_words

class InterviewQuestion(BaseModel):
    category: str = "probe_gap"   # probe_gap, verify_claim, depth
    question: str = ""
    target_requirement: str = ""
    rubric: Dict[str, str] = {}

class InterviewKitOutput(BaseModel):
    questions: List[InterviewQuestion] = []
    rubric: Dict[str, Any] = {}

class InterviewAgent:
    def __init__(self):
        self.llm = get_llm_provider()

    async def run(
        self,
        candidate_id: UUID,
        gaps: List[Dict[str, Any]],
        matches: List[Any],
        noise_flags: List[Any],
        verified_evidences: List[Any],
    ) -> Dict[str, Any]:
        nonce = secrets.token_hex(8)

        gap_text = "\n".join([
            f"- [{g['status']}] Req: {g.get('requirement_text', 'Unknown')} — Probe: {g.get('suggested_probe', '')}"
            for g in gaps
        ])
        demonstrated_claims = [
            e for e in verified_evidences
            if getattr(e, "grade", "") in ("demonstrated", "outcome_backed")
        ]
        claims_text = "\n".join([
            f"- {e.quote[:120]}" for e in demonstrated_claims[:5]
        ])

        context_data = f"""GAPS TO PROBE:
{gap_text or 'No gaps identified.'}

DEMONSTRATED CLAIMS TO VERIFY:
{claims_text or 'No demonstrated claims.'}
"""

        system_prompt = """You are the Interview Agent for RecruitRadar. Generate structured, objective technical interview questions.
NEVER mention: age, graduation dates, marital status, children, family plans, religion, caste, nationality, gender, sexual orientation, disability, or health.
Focus ONLY on technical competencies, project decisions, and professional skills."""

        user_prompt = f"""Generate gap-targeted interview questions based on:
<untrusted_document id="{nonce}">
{context_data}
</untrusted_document>

Produce 4-6 questions mixing: probe_gap (for MISSING/UNCERTAIN requirements), verify_claim (challenge demonstrated claims), depth (architectural trade-offs).
Each question must have a rubric with poor/good/excellent expectations."""

        extracted = await self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=InterviewKitOutput,
        )

        # Filter protected words from all questions
        cleaned_questions = []
        for q in extracted.questions:
            clean_text, _ = filter_protected_words(q.question)
            cleaned_questions.append({
                "category": q.category,
                "question": clean_text,
                "target_requirement": q.target_requirement,
                "rubric": q.rubric,
            })

        return {
            "questions": cleaned_questions,
            "rubric": extracted.rubric,
        }

interview_agent = InterviewAgent()
