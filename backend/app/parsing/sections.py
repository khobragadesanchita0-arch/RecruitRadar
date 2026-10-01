import re
from typing import Dict, List, Tuple

SECTION_PATTERNS = {
    "experience": [
        r"^(work\s+experience|professional\s+experience|employment\s+history|experience|work\s+history)",
    ],
    "education": [
        r"^(education|academic\s+background|qualifications|degrees)",
    ],
    "skills": [
        r"^(technical\s+skills|core\s+competencies|skills\s*(&|and)\s*tools|skills|technologies)",
    ],
    "projects": [
        r"^(key\s+projects|personal\s+projects|selected\s+projects|projects)",
    ],
    "summary": [
        r"^(professional\s+summary|executive\s+summary|about\s+me|summary|profile|objective)",
    ],
}

def extract_sections(text: str) -> Dict[str, str]:
    lines = text.split("\n")
    sections: Dict[str, List[str]] = {"general": []}
    current_section = "general"
    
    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
            
        # Check if line is a section header (short line, matches header pattern)
        header_matched = None
        if len(cleaned_line) < 40:
            lower_line = cleaned_line.lower().rstrip(":")
            for sec_name, patterns in SECTION_PATTERNS.items():
                for pat in patterns:
                    if re.match(pat, lower_line, re.IGNORECASE):
                        header_matched = sec_name
                        break
                if header_matched:
                    break
                    
        if header_matched:
            current_section = header_matched
            if current_section not in sections:
                sections[current_section] = []
        else:
            sections[current_section].append(cleaned_line)
            
    return {sec: "\n".join(lines) for sec, lines in sections.items() if lines}
