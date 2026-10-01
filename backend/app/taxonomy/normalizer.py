import json
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.llm.router import get_llm_provider

class SkillNormalizer:
    def __init__(self):
        curr_dir = Path(__file__).parent
        skills_path = curr_dir / "seed" / "skills.json"
        aliases_path = curr_dir / "seed" / "aliases.json"
        
        self.skills: List[Dict[str, Any]] = []
        self.aliases: Dict[str, str] = {}
        self.skill_ids: Dict[str, str] = {}  # canonical_name.lower() -> uuid
        
        if skills_path.exists():
            with open(skills_path, "r", encoding="utf-8") as f:
                self.skills = json.load(f)
                for s in self.skills:
                    c_name = s["canonical_name"]
                    s_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"skill.{c_name.lower()}"))
                    s["id"] = s_id
                    self.skill_ids[c_name.lower()] = s_id
                    
        if aliases_path.exists():
            with open(aliases_path, "r", encoding="utf-8") as f:
                self.aliases = {k.lower(): v for k, v in json.load(f).items()}
                
    def get_skill_id(self, canonical_name: str) -> str:
        return self.skill_ids.get(canonical_name.lower(), str(uuid.uuid5(uuid.NAMESPACE_DNS, f"skill.{canonical_name.lower()}")))

    async def normalize(self, raw_mention: str) -> Dict[str, Any]:
        """
        Normalizes raw skill mention to canonical skill:
        1. Direct canonical match
        2. Alias dictionary
        3. Embedding nearest neighbor (cos >= 0.80)
        4. Confidence < 0.70 => unmapped
        """
        raw_clean = raw_mention.strip()
        raw_lower = raw_clean.lower()
        
        # 1. Direct canonical match
        if raw_lower in self.skill_ids:
            canonical = next(s["canonical_name"] for s in self.skills if s["canonical_name"].lower() == raw_lower)
            return {
                "raw": raw_clean,
                "canonical_name": canonical,
                "skill_id": self.skill_ids[raw_lower],
                "method": "canonical",
                "confidence": 1.0,
            }
            
        # 2. Alias match
        if raw_lower in self.aliases:
            canonical = self.aliases[raw_lower]
            return {
                "raw": raw_clean,
                "canonical_name": canonical,
                "skill_id": self.get_skill_id(canonical),
                "method": "exact_alias",
                "confidence": 1.0,
            }
            
        # 3. Embedding cosine match
        llm = get_llm_provider()
        candidates = [s["canonical_name"] for s in self.skills]
        if candidates:
            embeddings = await llm.embed([raw_clean] + candidates)
            target_vec = embeddings[0]
            cand_vecs = embeddings[1:]
            
            best_cos = -1.0
            best_idx = -1
            for idx, vec in enumerate(cand_vecs):
                dot = sum(a * b for a, b in zip(target_vec, vec))
                norm_a = math.sqrt(sum(a * a for a in target_vec)) or 1.0
                norm_b = math.sqrt(sum(b * b for b in vec)) or 1.0
                cos = dot / (norm_a * norm_b)
                if cos > best_cos:
                    best_cos = cos
                    best_idx = idx
                    
            if best_cos >= 0.80 and best_idx >= 0:
                canonical = candidates[best_idx]
                return {
                    "raw": raw_clean,
                    "canonical_name": canonical,
                    "skill_id": self.get_skill_id(canonical),
                    "method": "embedding",
                    "confidence": round(best_cos, 3),
                }
                
        # Unmapped if confidence < 0.70
        return {
            "raw": raw_clean,
            "canonical_name": None,
            "skill_id": None,
            "method": "unmapped",
            "confidence": 0.0,
        }

skill_normalizer = SkillNormalizer()
