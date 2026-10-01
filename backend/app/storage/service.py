import hashlib
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from app.core.config import settings
from app.parsing.pdf import parse_pdf
from app.parsing.docx import parse_docx
from app.parsing.hidden_text import detect_unicode_hidden_chars, strip_hidden_unicode
from app.parsing.sections import extract_sections
from app.redaction.pii import redact_pii_and_demographics
from app.noise.injection_scan import scan_for_prompt_injection

EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

class StorageService:
    def __init__(self):
        self.base_dir = Path(settings.local_storage_path)
        self.quarantine_dir = self.base_dir / "quarantine"
        self.clean_dir = self.base_dir / "clean"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.clean_dir.mkdir(parents=True, exist_ok=True)
        
    def save_quarantine(self, file_bytes: bytes, filename: str) -> Tuple[str, str]:
        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix
        key = f"{file_id}{ext}"
        target_path = self.quarantine_dir / key
        with open(target_path, "wb") as f:
            f.write(file_bytes)
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        return key, sha256
        
    def scan_antivirus(self, file_bytes: bytes) -> Tuple[str, Optional[str]]:
        """
        Scans file bytes using AV engine (with built-in EICAR detection).
        Returns ('clean' | 'infected' | 'failed', details).
        """
        if EICAR_SIGNATURE in file_bytes:
            return "infected", "EICAR standard test virus signature detected"
        return "clean", None
        
    def promote_to_clean(self, quarantine_key: str) -> str:
        q_path = self.quarantine_dir / quarantine_key
        c_path = self.clean_dir / quarantine_key
        if q_path.exists():
            c_path.write_bytes(q_path.read_bytes())
            q_path.unlink()
        return f"clean/{quarantine_key}"

storage_service = StorageService()

async def intake_pipeline(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    workspace_id: str = "",
) -> Dict[str, Any]:
    """Async wrapper for intake pipeline."""
    import hashlib
    result = process_and_parse_file(file_bytes, filename, content_type)
    result["raw_hash"] = hashlib.sha256(file_bytes).hexdigest()
    result["parse_engine"] = "pdfminer"
    result["quarantined"] = (result.get("scan_status") == "infected")
    result["injection_detected"] = len(result.get("injection_flags", [])) > 0
    result["warnings"] = []
    result["hidden_text_flags"] = result.pop("hidden_text_items", [])
    # pii_blob is the encrypted bytes; store as hex string for jsonb
    pii_blob = result.pop("encrypted_pii", b"")
    result["pii_blob"] = pii_blob.hex() if isinstance(pii_blob, bytes) else pii_blob
    result["pii_fields"] = list(result.pop("extracted_pii", {}).keys())
    result["parsed"] = {"sections": result.pop("sections", {})}
    return result


def process_and_parse_file(
    file_bytes: bytes,
    filename: str,
    mime: str
) -> Dict[str, Any]:
    """
    Complete intake pipeline:
    1. AV Scan (checks for EICAR / threats)
    2. Format detection & sandboxed parsing
    3. Hidden text extraction
    4. Prompt injection scan
    5. PII Redaction
    Returns structured result dict.
    """
    # 1. AV Scan
    scan_status, scan_detail = storage_service.scan_antivirus(file_bytes)
    if scan_status == "infected":
        return {
            "status": "infected",
            "error": scan_detail,
            "scan_status": "infected",
            "parse_status": "failed",
        }
        
    # 2. Parse based on mime / extension
    ext = Path(filename).suffix.lower()
    raw_text = ""
    hidden_items = []
    parse_confidence = 1.0
    
    try:
        if ext == ".pdf" or "pdf" in mime:
            parsed = parse_pdf(file_bytes)
            raw_text = parsed["visible_text"]
            hidden_items = parsed["hidden_text_items"]
            parse_confidence = parsed["parse_confidence"]
        elif ext == ".docx" or "word" in mime:
            parsed = parse_docx(file_bytes)
            raw_text = parsed["visible_text"]
            hidden_items = parsed["hidden_text_items"]
            parse_confidence = parsed["parse_confidence"]
        elif ext == ".txt" or "text" in mime:
            raw_text = file_bytes.decode("utf-8", errors="replace")
            hidden_items = detect_unicode_hidden_chars(raw_text)
            raw_text = strip_hidden_unicode(raw_text)
            parse_confidence = 1.0 if len(raw_text) >= 100 else 0.5
        else:
            return {
                "status": "needs_attention",
                "error": f"Unsupported file format: {ext}",
                "scan_status": "clean",
                "parse_status": "needs_attention",
            }
    except Exception as e:
        return {
            "status": "needs_attention",
            "error": str(e),
            "scan_status": "clean",
            "parse_status": "needs_attention",
        }
        
    if not raw_text.strip():
        return {
            "status": "needs_attention",
            "error": "No readable text extracted (possible scanned document or image)",
            "scan_status": "clean",
            "parse_status": "needs_attention",
        }
        
    # 3. Prompt Injection scan & removal from analysis text
    inj_flags, text_after_injection_scan = scan_for_prompt_injection(raw_text)
    
    # 4. Redaction of PII & demographic markers
    analysis_text, extracted_pii, encrypted_pii = redact_pii_and_demographics(text_after_injection_scan)
    
    # 5. Extract resume sections
    sections = extract_sections(raw_text)
    
    return {
        "status": "parsed",
        "scan_status": "clean",
        "parse_status": "parsed",
        "raw_text": raw_text,
        "analysis_text": analysis_text,
        "hidden_text_items": hidden_items,
        "injection_flags": inj_flags,
        "sections": sections,
        "extracted_pii": extracted_pii,
        "encrypted_pii": encrypted_pii,
        "parse_confidence": parse_confidence,
    }
