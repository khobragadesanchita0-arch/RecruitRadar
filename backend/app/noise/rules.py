from typing import Any, Dict, List, Optional
from app.schemas.contracts import NoiseFlag, EvidenceItem
from app.noise.features import (
    compute_term_frequencies, compute_type_token_ratio,
    compute_jaccard_similarity, split_sentences, TECH_RELEASE_YEARS
)
from app.noise.injection_scan import scan_for_prompt_injection

def evaluate_skill_stuffing(
    skills_listed_count: int,
    skills_with_context_count: int,
) -> Optional[NoiseFlag]:
    if skills_listed_count < 25:
        return None
        
    context_ratio = skills_with_context_count / max(1, skills_listed_count)
    
    if skills_listed_count >= 40 and context_ratio < 0.10:
        return NoiseFlag(
            type="SKILL_STUFFING",
            severity="HIGH",
            detail=f"{skills_listed_count} skills listed, only {skills_with_context_count} with context (ratio: {context_ratio:.2f})",
            metrics={
                "skills_listed": skills_listed_count,
                "skills_with_context": skills_with_context_count,
                "context_ratio": round(context_ratio, 3),
            }
        )
    elif skills_listed_count >= 25 and context_ratio < 0.25:
        return NoiseFlag(
            type="SKILL_STUFFING",
            severity="MED",
            detail=f"{skills_listed_count} skills listed, only {skills_with_context_count} with context (ratio: {context_ratio:.2f})",
            metrics={
                "skills_listed": skills_listed_count,
                "skills_with_context": skills_with_context_count,
                "context_ratio": round(context_ratio, 3),
            }
        )
    return None

def evaluate_repeated_terms(section_texts: Dict[str, str]) -> List[NoiseFlag]:
    flags: List[NoiseFlag] = []
    for sec_name, text in section_texts.items():
        freqs = compute_term_frequencies(text)
        excessive = {term: count for term, count in freqs.items() if count >= 8}
        if excessive:
            top_term = max(excessive.items(), key=lambda x: x[1])
            severity = "MED" if top_term[1] >= 15 else "LOW"
            flags.append(NoiseFlag(
                type="REPEATED_TERMS",
                severity=severity,
                detail=f"Term '{top_term[0]}' repeated {top_term[1]}x in {sec_name} section",
                metrics={"section": sec_name, "repeated_terms": excessive}
            ))
            
        if sec_name.lower() in ("skills", "technical skills"):
            ttr = compute_type_token_ratio(text)
            if ttr < 0.5:
                flags.append(NoiseFlag(
                    type="REPEATED_TERMS",
                    severity="LOW",
                    detail=f"Low lexical diversity in skills section (type/token ratio: {ttr:.2f})",
                    metrics={"section": sec_name, "type_token_ratio": round(ttr, 3)}
                ))
    return flags

def evaluate_jd_copy(resume_text: str, jd_text: str) -> Optional[NoiseFlag]:
    resume_sentences = split_sentences(resume_text)
    jd_sentences = split_sentences(jd_text)
    
    if not resume_sentences or not jd_sentences:
        return None
        
    copied_count = 0
    for r_sent in resume_sentences:
        for jd_sent in jd_sentences:
            if compute_jaccard_similarity(r_sent, jd_sent) >= 0.85:
                copied_count += 1
                break
                
    ratio = copied_count / len(resume_sentences)
    if ratio >= 0.80:
        return NoiseFlag(
            type="JD_COPY",
            severity="HIGH",
            detail=f"{copied_count}/{len(resume_sentences)} resume sentences closely match JD sentences ({ratio*100:.1f}%)",
            metrics={"matched_sentences": copied_count, "total_sentences": len(resume_sentences), "ratio": round(ratio, 3)}
        )
    elif ratio >= 0.60:
        return NoiseFlag(
            type="JD_COPY",
            severity="MED",
            detail=f"{copied_count}/{len(resume_sentences)} resume sentences closely match JD sentences ({ratio*100:.1f}%)",
            metrics={"matched_sentences": copied_count, "total_sentences": len(resume_sentences), "ratio": round(ratio, 3)}
        )
    return None

def evaluate_hidden_text_flags(hidden_text_items: List[Dict[str, Any]]) -> List[NoiseFlag]:
    flags: List[NoiseFlag] = []
    if not hidden_text_items:
        return flags
        
    for item in hidden_text_items:
        text = item.get("text", "")
        reason = item.get("reason", "unknown")
        # Check if hidden text contains instructions or prompt injection
        inj_flags, _ = scan_for_prompt_injection(text)
        severity = "HIGH" if inj_flags or item.get("contains_keywords") else "MED"
        flags.append(NoiseFlag(
            type="HIDDEN_TEXT",
            severity=severity,
            detail=f"Hidden text detected: {reason} ('{text[:40]}...')",
            metrics=item
        ))
    return flags

def evaluate_timeline_anachronisms(
    evidences: List[EvidenceItem],
    skills_map: Dict[str, str],  # skill_id -> canonical_name
) -> List[NoiseFlag]:
    flags: List[NoiseFlag] = []
    for e in evidences:
        skill_name = skills_map.get(str(e.skill_id), "").lower()
        if not skill_name:
            continue
            
        release_yr = TECH_RELEASE_YEARS.get(skill_name)
        if release_yr and e.last_used and e.duration_months:
            start_yr = e.last_used.year - int(e.duration_months / 12)
            if start_yr < release_yr:
                flags.append(NoiseFlag(
                    type="TIMELINE_ANACHRONISM",
                    severity="LOW",
                    detail=f"Claimed experience with {skill_name} in {start_yr}, but released in {release_yr}",
                    metrics={
                        "skill": skill_name,
                        "claimed_start_year": start_yr,
                        "release_year": release_yr
                    }
                ))
    return flags

def run_noise_detection(
    resume_text: str,
    jd_text: str,
    section_texts: Dict[str, str],
    skills_listed_count: int,
    skills_with_context_count: int,
    hidden_text_items: List[Dict[str, Any]],
    evidences: List[EvidenceItem],
    skills_map: Dict[str, str],
) -> List[NoiseFlag]:
    """
    Runs full noise detection pipeline over candidate data.
    """
    flags: List[NoiseFlag] = []
    
    # 1. Prompt Injection
    inj_flags, _ = scan_for_prompt_injection(resume_text)
    flags.extend(inj_flags)
    
    # 2. Skill Stuffing
    stuffing = evaluate_skill_stuffing(skills_listed_count, skills_with_context_count)
    if stuffing:
        flags.append(stuffing)
        
    # 3. Repeated Terms
    flags.extend(evaluate_repeated_terms(section_texts))
    
    # 4. JD Copy
    jd_copy = evaluate_jd_copy(resume_text, jd_text)
    if jd_copy:
        flags.append(jd_copy)
        
    # 5. Hidden Text
    flags.extend(evaluate_hidden_text_flags(hidden_text_items))
    
    # 6. Timeline Anachronism
    flags.extend(evaluate_timeline_anachronisms(evidences, skills_map))
    
    return flags
