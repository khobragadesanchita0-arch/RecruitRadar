from datetime import date
from typing import Any, Dict, List, Tuple
from uuid import UUID
from app.schemas.contracts import Requirement, EvidenceItem, NoiseFlag, RequirementMatch
from app.scoring.engine import score_candidate

class MatcherAgent:
    def run(
        self,
        candidate_id: UUID,
        requirements: List[Requirement],
        evidences: List[EvidenceItem],
        noise_flags: List[NoiseFlag],
        today: date,
        parse_confidence: float = 1.0,
        verifier_pass_rate: float = 1.0,
    ) -> Tuple[int, float, List[RequirementMatch], List[Dict[str, Any]], str]:
        """
        Pure deterministic matching and scoring. No LLM used for score calculation.
        """
        return score_candidate(
            candidate_id=candidate_id,
            requirements=requirements,
            evidences=evidences,
            noise_flags=noise_flags,
            today=today,
            parse_confidence=parse_confidence,
            verifier_pass_rate=verifier_pass_rate,
        )

matcher_agent = MatcherAgent()
