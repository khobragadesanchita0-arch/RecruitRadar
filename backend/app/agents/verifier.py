import difflib
import re
from typing import Optional, Tuple
from app.schemas.contracts import EvidenceItem

def normalize_text_for_span(text: str) -> str:
    # Collapse multiple whitespaces/newlines and lower
    return " ".join(text.split()).lower()

def verify_verbatim_quote(
    quote: str,
    visible_resume_text: str,
) -> Tuple[bool, int, int]:
    """
    Verifies that quote exists in visible_resume_text.
    Allows exact substring match or whitespace-normalized fuzzy match >= 0.95.
    Returns (is_verified, span_start, span_end).
    """
    if not quote or not visible_resume_text:
        return False, 0, 0
        
    # 1. Direct exact match
    idx = visible_resume_text.find(quote)
    if idx != -1:
        return True, idx, idx + len(quote)
        
    # 2. Case-insensitive match
    lower_resume = visible_resume_text.lower()
    lower_quote = quote.lower()
    idx = lower_resume.find(lower_quote)
    if idx != -1:
        return True, idx, idx + len(quote)
        
    # 3. Normalized whitespace match
    norm_quote = normalize_text_for_span(quote)
    norm_resume = normalize_text_for_span(visible_resume_text)
    idx = norm_resume.find(norm_quote)
    if idx != -1:
        # Approximate offset in original text
        return True, idx, idx + len(quote)
        
    # 4. Fuzzy match >= 0.95 for punctuation/spacing differences
    # Search sliding windows of length len(quote) in visible_resume_text
    q_len = len(norm_quote)
    if q_len > 15:
        step = max(1, q_len // 4)
        for i in range(0, len(norm_resume) - q_len + 1, step):
            window = norm_resume[i:i + q_len]
            ratio = difflib.SequenceMatcher(None, norm_quote, window).ratio()
            if ratio >= 0.95:
                return True, i, i + len(quote)
                
    return False, 0, 0

def verify_evidence_items(
    items: list[EvidenceItem],
    visible_resume_text: str,
) -> Tuple[list[EvidenceItem], int]:
    """
    Verifies a list of evidence items.
    Discards non-verbatim items, sets verified=True on verified items.
    Returns (verified_items, verifier_rejections_count).
    """
    verified_list: list[EvidenceItem] = []
    rejections = 0
    
    for item in items:
        is_valid, start, end = verify_verbatim_quote(item.quote, visible_resume_text)
        if is_valid:
            item.verified = True
            item.span_start = start
            item.span_end = end
            verified_list.append(item)
        else:
            item.verified = False
            rejections += 1
            
    return verified_list, rejections
