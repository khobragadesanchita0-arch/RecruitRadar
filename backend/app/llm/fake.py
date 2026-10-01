import hashlib
import json
import math
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel
from app.llm.provider import LLMProvider, LLMResponse, LLMUsage

T = TypeVar("T", bound=BaseModel)

class FakeLLM(LLMProvider):
    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _hash_vector(self, text: str) -> List[float]:
        """Generates deterministic pseudo-embedding vector of dimension self.dim from text."""
        tokens = text.lower().split()
        vec = [0.0] * self.dim
        for i, tok in enumerate(tokens):
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % self.dim
            vec[idx] += 1.0 / (1.0 + i)
            
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_vector(t) for t in texts]

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 250,
        temperature: float = 0.0,
    ) -> LLMResponse:
        tokens_est = len(user_prompt.split()) + len(system_prompt.split())
        return LLMResponse(
            content="Structured evaluation completed based on deterministic evidence.",
            usage=LLMUsage(
                prompt_tokens=tokens_est,
                completion_tokens=15,
                total_tokens=tokens_est + 15,
                estimated_cost_usd=0.0001,
            ),
            model="fake-llm-v2"
        )

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """
        Deterministic mock generator for all pipeline schemas:
        - JD Requirements extraction
        - Evidence extraction
        - Skill Normalization
        - Interview questions
        """
        schema_name = schema.__name__
        
        # 1. JD Analysis output
        if "JDAnalysis" in schema_name or "Requirement" in schema_name:
            # Deterministic requirement extraction from user_prompt
            # Find bullet points or skill names
            extracted_reqs = []
            keywords = ["Python", "Kubernetes", "Kafka", "PostgreSQL", "Docker", "AWS", "Go", "React", "TypeScript", "Distributed Systems"]
            found = [kw for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", user_prompt, re.I)]
            if not found:
                found = ["Software Engineering", "Problem Solving"]
                
            for i, kw in enumerate(found):
                kind = "must" if i < 3 else "nice"
                extracted_reqs.append({
                    "text": f"{3 if i == 0 else 2}+ years practical experience with {kw}",
                    "skill_ids": [],
                    "kind": kind,
                    "weight": 1.0 if kind == "must" else 0.5,
                    "min_months": 36 if i == 0 else 24,
                })
            
            payload = {
                "seniority": "Senior" if "senior" in user_prompt.lower() else "Mid-level",
                "requirements": extracted_reqs,
                "jd_health_flags": [],
            }
            try:
                return schema.model_validate(payload)
            except Exception:
                pass

        # 2. Evidence extraction output
        if "Evidence" in schema_name:
            # Find verbatim sentences in the user_prompt
            sentences = re.split(r"(?<=[.!?])\s+|\n+", user_prompt)
            items = []
            for s in sentences:
                st = s.strip()
                if len(st) > 20 and not st.startswith("<") and not st.startswith("[REDACTED"):
                    grade = "contextual"
                    if any(num in st for num in ["%", "ms", "reduction", "scale", "cutting", "improved"]):
                        grade = "outcome_backed"
                    elif any(verb in st.lower() for verb in ["built", "designed", "deployed", "implemented", "managed"]):
                        grade = "demonstrated"
                        
                    items.append({
                        "quote": st,
                        "grade": grade,
                        "duration_months": 24,
                        "role_ref": "Software Engineer (Recent)",
                        "outcome_text": st if grade == "outcome_backed" else None,
                    })
                    if len(items) >= 5:
                        break
                        
            payload = {"evidence_items": items}
            try:
                return schema.model_validate(payload)
            except Exception:
                pass

        # 3. Interview Kit output
        if "Interview" in schema_name:
            payload = {
                "questions": [
                    {
                        "category": "probe_gap",
                        "question": "Can you describe a challenging scenario you encountered with system scalability?",
                        "target_requirement": "Distributed Systems",
                        "rubric": {"poor": "Generic theoretical answer", "good": "Details real failure mode and remediation"},
                    },
                    {
                        "category": "verify_claim",
                        "question": "Walk me through how you implemented your recent backend architecture.",
                        "target_requirement": "Architecture",
                        "rubric": {"poor": "Vague about personal role", "good": "Articulates trade-offs and tech choices"},
                    }
                ],
                "rubric": {"pass_score": 70}
            }
            try:
                return schema.model_validate(payload)
            except Exception:
                pass

        # Default fallback
        try:
            return schema.model_validate({})
        except Exception:
            # Construct dummy fields
            data = {}
            for field_name, field in schema.model_fields.items():
                if field.annotation == str:
                    data[field_name] = "default"
                elif field.annotation == int:
                    data[field_name] = 1
                elif field.annotation == float:
                    data[field_name] = 1.0
                elif field.annotation == list or getattr(field.annotation, "__origin__", None) == list:
                    data[field_name] = []
                elif field.annotation == dict or getattr(field.annotation, "__origin__", None) == dict:
                    data[field_name] = {}
            return schema.model_validate(data)
