from typing import Any, Dict, List, Tuple
from app.schemas.contracts import Requirement, EvidenceItem, NoiseFlag

def generate_keyword_stuffed_skills(base_text: str, jd_keywords: List[str]) -> str:
    """Variant a: Appending 50 JD keywords to the skills section."""
    skills_block = "\nSkills: " + ", ".join(jd_keywords[:50])
    return base_text + skills_block

def generate_hidden_keywords(base_text: str, jd_keywords: List[str]) -> Tuple[str, List[Dict[str, Any]]]:
    """Variant b: Hidden keywords (white-on-white or tiny font)."""
    hidden_text = " ".join(jd_keywords[:30])
    hidden_flags = [{
        "text": hidden_text,
        "reason": "white_on_white_text",
        "font_size": 1.0,
        "color": "#FFFFFF",
        "contains_keywords": True,
    }]
    return base_text, hidden_flags

def generate_repeated_keywords(base_text: str, target_keyword: str, count: int = 20) -> str:
    """Variant c: Keywords repeated 20×."""
    repeated_block = f"\nTechnical Summary: " + " ".join([target_keyword] * count)
    return base_text + repeated_block

def generate_jd_copy_summary(base_text: str, jd_text: str) -> str:
    """Variant d: JD paragraph pasted into candidate summary."""
    return f"Executive Summary:\n{jd_text}\n\n" + base_text
