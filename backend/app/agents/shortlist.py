from typing import Any, Dict, List, Set, Tuple
from uuid import UUID
from app.schemas.contracts import ShortlistEntry, EvidenceItem, RequirementMatch, NoiseFlag
from app.scoring.engine import rank_candidates
from app.redaction.protected import filter_protected_words

class ShortlistAgent:
    def run(
        self,
        candidates_scored_data: List[Tuple[UUID, int, float, List[RequirementMatch], List[NoiseFlag], List[Dict[str, Any]], str]],
        evidences_by_candidate: Dict[UUID, List[EvidenceItem]],
        must_req_ids: Set[UUID],
    ) -> List[ShortlistEntry]:
        """
        Ranks candidates deterministically.
        Applies protected attribute filtering on all rationales.
        """
        # Filter protected words from rationales
        sanitized_data = []
        for cand_id, fit, conf, matches, flags, gaps, rat in candidates_scored_data:
            clean_rat, _ = filter_protected_words(rat)
            # Ensure word count <= 60 words
            words = clean_rat.split()
            if len(words) > 60:
                clean_rat = " ".join(words[:57]) + "..."
            sanitized_data.append((cand_id, fit, conf, matches, flags, gaps, clean_rat))
            
        entries = rank_candidates(sanitized_data, evidences_by_candidate, must_req_ids)
        return entries

shortlist_agent = ShortlistAgent()
