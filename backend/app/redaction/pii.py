import json
import re
from typing import Any, Dict, Tuple
from app.core.security import encrypt_pii

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b"
)
DOB_AGE_PATTERNS = [
    re.compile(r"\b(d\.?o\.?b\.?|date\s+of\s+birth)\s*[:\-]?\s*([^\r\n]+)", re.IGNORECASE),
    re.compile(r"\b(age)\s*[:\-]?\s*([0-9]{1,2})\b", re.IGNORECASE),
    re.compile(r"\b([0-9]{1,2})\s*years?\s*old\b", re.IGNORECASE),
]
DEMOGRAPHIC_PATTERNS = [
    re.compile(r"\b(gender|sex)\s*[:\-]?\s*([^\r\n]+)", re.IGNORECASE),
    re.compile(r"\b(marital\s*status)\s*[:\-]?\s*([^\r\n]+)", re.IGNORECASE),
    re.compile(r"\b(nationality|citizenship)\s*[:\-]?\s*([^\r\n]+)", re.IGNORECASE),
    re.compile(r"\b(religion|caste)\s*[:\-]?\s*([^\r\n]+)", re.IGNORECASE),
]

def redact_pii_and_demographics(text: str) -> Tuple[str, Dict[str, Any], bytes]:
    """
    Extracts PII into a dictionary, returns redacted analysis_text and encrypted PII bytea.
    """
    extracted_pii: Dict[str, Any] = {
        "emails": [],
        "phones": [],
        "dob_age": [],
        "demographics": [],
        "name": None,
    }
    
    redacted = text
    
    # Extract emails
    emails = EMAIL_PATTERN.findall(redacted)
    if emails:
        extracted_pii["emails"] = emails
        redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)
        
    # Extract phones
    phones = PHONE_PATTERN.findall(redacted)
    if phones:
        valid_phones = [p for p in phones if not re.match(r"^\d{4}[-–]\d{4}$", p.strip())]
        if valid_phones:
            extracted_pii["phones"] = valid_phones
            for p in valid_phones:
                redacted = redacted.replace(p, "[REDACTED_PHONE]")
                
    # Extract DOB / Age
    for pat in DOB_AGE_PATTERNS:
        for match in pat.finditer(redacted):
            extracted_pii["dob_age"].append(match.group(0))
        redacted = pat.sub("[REDACTED_DOB_AGE]", redacted)
        
    # Extract Demographics (gender, marital status, nationality, religion)
    for pat in DEMOGRAPHIC_PATTERNS:
        for match in pat.finditer(redacted):
            extracted_pii["demographics"].append(match.group(0))
        redacted = pat.sub("[REDACTED_DEMOGRAPHICS]", redacted)
        
    # Extract Name from the first non-empty line
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        first_line = lines[0]
        words = first_line.split()
        if 2 <= len(words) <= 4 and all(w.isalpha() for w in words):
            extracted_pii["name"] = first_line
            name_pattern = re.compile(re.escape(first_line), re.IGNORECASE)
            redacted = name_pattern.sub("[REDACTED_NAME]", redacted)
            
    # Serialize and encrypt PII
    pii_json = json.dumps(extracted_pii)
    encrypted_bytes = encrypt_pii(pii_json)
    
    return redacted, extracted_pii, encrypted_bytes
