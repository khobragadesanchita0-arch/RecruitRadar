"""
Re-export protected word list from EEOC-protected topics.
Used to scan both LLM output AND JD text for prohibited language.
"""
import re
from typing import List, Tuple

# Words/phrases that could indicate discrimination or protected-topic probing
PROTECTED_TOPIC_PATTERNS: List[str] = [
    # Age
    r"\bage[d]?\b", r"\bolder\b", r"\byoung\b", r"\bfresh\s+graduate", r"\brecent\s+graduate",
    r"\byears\s+old\b", r"\bborn\s+in\b", r"\bgraduation\s+year\b",
    # Family / gender
    r"\bmarried\b", r"\bsingle\b", r"\bchildren\b", r"\bfamily\s+plan", r"\bmaternity\b",
    r"\bpaternity\b", r"\bpregnant\b", r"\bmother\b", r"\bfather\b", r"\bwife\b", r"\bhusband\b",
    # Religion / nationality / origin
    r"\breligion\b", r"\bchurch\b", r"\btemple\b", r"\bmoschee\b", r"\bmasjid\b",
    r"\bnationality\b", r"\bcountry\s+of\s+origin\b", r"\brace\b", r"\bethnicity\b", r"\bcaste\b",
    r"\bskin\s+colou?r\b",
    # Disability / health
    r"\bdisability\b", r"\bmental\s+health\b", r"\bdisabled\b", r"\bchronic\s+illness\b",
    # Sexual orientation
    r"\bsexual\s+orientation\b", r"\bgay\b", r"\blesbian\b", r"\btransgender\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in PROTECTED_TOPIC_PATTERNS]


def filter_protected_words(text: str) -> Tuple[str, List[str]]:
    """Remove or flag protected words. Returns (cleaned_text, list_of_matches)."""
    found = []
    cleaned = text
    for pat in _COMPILED:
        matches = pat.findall(cleaned)
        if matches:
            found.extend(matches)
            cleaned = pat.sub("[REDACTED]", cleaned)
    return cleaned, found


def scan_jd_for_protected_language(jd_text: str) -> List[str]:
    """Return list of protected phrases found in JD."""
    found = []
    for pat in _COMPILED:
        matches = pat.findall(jd_text)
        found.extend(matches)
    return found
