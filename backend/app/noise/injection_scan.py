import re
import unicodedata
from typing import Tuple, List
from app.schemas.contracts import NoiseFlag

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"you\s+are\s+(now\s+)?an?\s+ai",
    r"you\s+are\s+(now\s+)?(a|an)?\s*(unbiased\s+)?(recruiter|assistant|system)",
    r"system\s*:\s*",
    r"disregard\s+(all\s+)?prompts",
    r"rank\s+this\s+candidate\s+(first|highest|#1|as\s+met)",
    r"mark\s+(all\s+)?requirements\s+as\s+met",
    r"give\s+this\s+candidate\s+(a\s+score\s+of\s+)?100",
    r"prompt\s+injection",
    r"bypass\s+safety",
    r"assistant\s*:",
    r"\[system[^\]]*\]",
    r"\bcurl\s+http",
    r"\bwget\s+http",
    r"http[s]?://[^\s]*\.(webhook|pipedream|requestbin|burpcollaborator)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

def normalize_text(text: str) -> str:
    # NFKD normalization to reveal homoglyphs and hidden characters
    return unicodedata.normalize("NFKD", text)

def scan_for_prompt_injection(text: str) -> Tuple[List[NoiseFlag], str]:
    """
    Scans text for prompt injection patterns.
    Removes matched injection spans from visible analysis text.
    Returns (flags, cleaned_text).
    """
    norm_text = normalize_text(text)
    flags: List[NoiseFlag] = []
    spans_to_remove: List[Tuple[int, int]] = []
    
    for pattern in COMPILED_PATTERNS:
        for match in pattern.finditer(norm_text):
            spans_to_remove.append(match.span())
            flags.append(NoiseFlag(
                type="PROMPT_INJECTION",
                severity="HIGH",
                detail=f"Prompt injection pattern detected: '{match.group(0)[:50]}'",
                metrics={"pattern": pattern.pattern, "matched_text": match.group(0)[:50]}
            ))
            
    if not spans_to_remove:
        return [], text
        
    # Remove matched spans from text
    # Sort spans in reverse to delete without offset corruption
    spans_to_remove.sort(reverse=True)
    cleaned = list(text)
    for start, end in spans_to_remove:
        cleaned[start:end] = list("[REDACTED_INJECTION_PAYLOAD]")
        
    return flags, "".join(cleaned)
