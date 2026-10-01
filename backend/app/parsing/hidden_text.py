import re
from typing import Any, Dict, List, Tuple

ZERO_WIDTH_CHARS = {
    "\u200b": "ZERO_WIDTH_SPACE",
    "\u200c": "ZERO_WIDTH_NON_JOINER",
    "\u200d": "ZERO_WIDTH_JOINER",
    "\ufeff": "ZERO_WIDTH_NO_BREAK_SPACE",
}

UNICODE_TAG_PATTERN = re.compile(r"[\U000e0020-\U000e007f]")

def detect_unicode_hidden_chars(text: str) -> List[Dict[str, Any]]:
    hidden_findings = []
    
    # Check zero-width characters
    for char, name in ZERO_WIDTH_CHARS.items():
        count = text.count(char)
        if count > 0:
            hidden_findings.append({
                "type": "ZERO_WIDTH_CHARS",
                "character": name,
                "count": count,
                "reason": f"Found {count} zero-width character(s) ({name})",
            })
            
    # Check unicode tag characters (used for hidden steganography/prompts)
    tags = UNICODE_TAG_PATTERN.findall(text)
    if tags:
        # Convert tag characters back to ASCII to see hidden payload
        decoded_tag_chars = "".join([chr(ord(c) - 0xe0000) for c in tags if 0x20 <= ord(c) - 0xe0000 <= 0x7e])
        hidden_findings.append({
            "type": "UNICODE_TAGS",
            "count": len(tags),
            "reason": f"Found {len(tags)} Unicode tag characters",
            "text": decoded_tag_chars,
        })
        
    return hidden_findings

def strip_hidden_unicode(text: str) -> str:
    cleaned = text
    for char in ZERO_WIDTH_CHARS:
        cleaned = cleaned.replace(char, "")
    cleaned = UNICODE_TAG_PATTERN.sub("", cleaned)
    return cleaned
