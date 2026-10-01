from datetime import date
from typing import Any, Optional
from uuid import UUID
from app.schemas.contracts import (
    Requirement, EvidenceItem, RequirementMatch, NoiseFlag, ShortlistEntry
)
from app.scoring.config import (
    GRADE_WEIGHT, HALF_LIFE_MONTHS, MUST_SHARE, NICE_SHARE,
    NOISE_PEN, NOISE_PEN_CAP, INJECTION_SCORE_CAP,
    MET_THRESHOLD, PARTIAL_THRESHOLD, PARSE_CONFIDENCE_UNCERTAIN,
    CONFIDENCE_PARSE_WEIGHT, CONFIDENCE_COVERAGE_WEIGHT,
    CONFIDENCE_UNCERTAIN_WEIGHT, CONFIDENCE_VERIFIER_WEIGHT
)

def months_since(last_used: Optional[date], today: date) -> float:
    if last_used is None:
        return 0.0
    return max(0.0, (today.year - last_used.year) * 12 + (today.month - last_used.month))

def compute_recency(e: EvidenceItem, today: date) -> float:
    if e.last_used is None:
        return 0.5  # Unknown last_used => treated as unknown (recency factor 0.5)
    months = months_since(e.last_used, today)
    return 0.5 ** (months / HALF_LIFE_MONTHS)

def compute_duration(e: EvidenceItem, r: Requirement) -> float:
    if r.min_months is None or e.duration_months is None:
        return 1.0
    if r.min_months <= 0:
        return 1.0
    return min(1.0, float(e.duration_months) / float(r.min_months))

def compute_evidence_value(e: EvidenceItem, r: Requirement, today: date) -> float:
    if not e.verified:
        return 0.0
    grade_w = GRADE_WEIGHT.get(e.grade, 0.0)
    rec = compute_recency(e, today)
    dur = compute_duration(e, r)
    return grade_w * rec * dur

def compute_requirement_strength(
    r: Requirement,
    evidences: list[EvidenceItem],
    today: date,
) -> tuple[float, list[UUID], bool]:
    """
    Computes strength for requirement r over verified evidence matching r.skill_ids.
    Uses diminishing returns: strength(c, r) = 1 - Π_e (1 - value(e, r))
    Returns (strength, matched_evidence_ids, has_only_listed)
    """
    target_skills = set(r.skill_ids)
    matching_evidences = [e for e in evidences if e.skill_id in target_skills]
    
    # Check if only 'listed' evidence exists for this requirement
    has_any_evidence = len(matching_evidences) > 0
    has_only_listed = has_any_evidence and all(e.grade == "listed" for e in matching_evidences)
    
    # Only verified evidence counts for scoring
    verified_evidences = [e for e in matching_evidences if e.verified]
    
    prod = 1.0
    matched_ids: list[UUID] = []
    
    for e in verified_evidences:
        val = compute_evidence_value(e, r, today)
        prod *= (1.0 - val)
        matched_ids.append(e.id)
        
    strength = 1.0 - prod
    return max(0.0, min(1.0, strength)), matched_ids, has_only_listed

def compute_requirement_status(
    strength: float,
    parse_confidence: float = 1.0,
    has_only_listed: bool = False,
    low_conf_semantic: bool = False,
) -> str:
    """
    MET if strength >= 0.65
    PARTIAL if 0.25 <= strength < 0.65
    else: UNCERTAIN if parse_confidence < 0.6 or only related evidence is listed or low-conf semantic; else MISSING
    """
    if strength >= MET_THRESHOLD:
        return "MET"
    if strength >= PARTIAL_THRESHOLD:
        return "PARTIAL"
    
    if parse_confidence < PARSE_CONFIDENCE_UNCERTAIN or has_only_listed or low_conf_semantic:
        return "UNCERTAIN"
        
    return "MISSING"

def score_candidate(
    candidate_id: UUID,
    requirements: list[Requirement],
    evidences: list[EvidenceItem],
    noise_flags: list[NoiseFlag],
    today: date,
    parse_confidence: float = 1.0,
    verifier_pass_rate: float = 1.0,
) -> tuple[int, float, list[RequirementMatch], list[dict[str, Any]], str]:
    """
    Computes deterministic fit_score, confidence, matches, gaps, and rationale.
    """
    must_reqs = [r for r in requirements if r.kind == "must"]
    nice_reqs = [r for r in requirements if r.kind == "nice"]
    
    total_must_weight = sum(r.weight for r in must_reqs) or 1.0
    total_nice_weight = sum(r.weight for r in nice_reqs) or 1.0
    
    matches: list[RequirementMatch] = []
    gaps: list[dict[str, Any]] = []
    
    must_score = 0.0
    nice_score = 0.0
    
    met_count = 0
    non_listed_verified_must_count = 0
    uncertain_must_count = 0
    
    for r in must_reqs:
        strength, matched_ids, has_only_listed = compute_requirement_strength(r, evidences, today)
        status = compute_requirement_status(strength, parse_confidence, has_only_listed)
        norm_weight = r.weight / total_must_weight
        must_score += norm_weight * strength
        
        matches.append(RequirementMatch(
            requirement_id=r.id,
            status=status,
            strength=strength,
            evidence_ids=matched_ids
        ))
        
        if status == "MET":
            met_count += 1
        elif status in ("UNCERTAIN", "MISSING", "PARTIAL"):
            gaps.append({
                "requirement_id": str(r.id),
                "requirement_text": r.text,
                "status": status,
                "suggested_probe": f"Probe practical experience with {r.text} and project impact."
            })
            
        if status == "UNCERTAIN":
            uncertain_must_count += 1
            
        # Check non-listed verified evidence for coverage
        for e in evidences:
            if e.skill_id in set(r.skill_ids) and e.verified and e.grade != "listed":
                non_listed_verified_must_count += 1
                break

    for r in nice_reqs:
        strength, matched_ids, has_only_listed = compute_requirement_strength(r, evidences, today)
        status = compute_requirement_status(strength, parse_confidence, has_only_listed)
        norm_weight = r.weight / total_nice_weight
        nice_score += norm_weight * strength
        
        matches.append(RequirementMatch(
            requirement_id=r.id,
            status=status,
            strength=strength,
            evidence_ids=matched_ids
        ))
        if status in ("UNCERTAIN", "MISSING"):
            gaps.append({
                "requirement_id": str(r.id),
                "requirement_text": r.text,
                "status": status,
                "suggested_probe": f"Explore exposure to nice-to-have skill: {r.text}."
            })

    # Raw fit calculation
    if not nice_reqs:
        raw_fit = must_score
    else:
        raw_fit = MUST_SHARE * must_score + NICE_SHARE * nice_score

    # Noise penalties (only active, undismissed flags)
    active_flags = [f for f in noise_flags if not f.dismissed]
    noise_pen = min(NOISE_PEN_CAP, sum(NOISE_PEN.get(f.severity, 0.0) for f in active_flags))
    
    fit_score = round(100.0 * raw_fit * (1.0 - noise_pen))
    
    # Prompt injection score cap
    if any(f.type == "PROMPT_INJECTION" for f in active_flags):
        fit_score = min(fit_score, INJECTION_SCORE_CAP)
        
    fit_score = max(0, min(100, fit_score))
    
    # Confidence calculation:
    # confidence = 0.35*parse_quality + 0.35*evidence_coverage + 0.20*(1 - uncertain_ratio) + 0.10*verifier_pass_rate
    must_count = len(must_reqs) or 1
    evidence_coverage = non_listed_verified_must_count / must_count
    uncertain_ratio = uncertain_must_count / must_count
    
    confidence = (
        CONFIDENCE_PARSE_WEIGHT * parse_confidence
        + CONFIDENCE_COVERAGE_WEIGHT * evidence_coverage
        + CONFIDENCE_UNCERTAIN_WEIGHT * (1.0 - uncertain_ratio)
        + CONFIDENCE_VERIFIER_WEIGHT * verifier_pass_rate
    )
    confidence = max(0.0, min(1.0, round(confidence, 3)))
    
    # Build concise, structured rationale (<=60 words, strictly data-derived)
    must_met = len([m for m in matches if m.status == "MET" and any(r.id == m.requirement_id and r.kind == "must" for r in must_reqs)])
    rationale = f"Candidate satisfies {must_met}/{len(must_reqs)} must requirements with verified evidence (Fit: {fit_score}%)."
    if active_flags:
        flag_types = ", ".join(set(f.type for f in active_flags))
        rationale += f" Penalized for noise flags ({flag_types})."
    if gaps:
        rationale += f" Identified {len(gaps)} potential skill gaps to probe in interviews."
        
    return fit_score, confidence, matches, gaps, rationale

def rank_candidates(
    candidates_data: list[tuple[UUID, int, float, list[RequirementMatch], list[NoiseFlag], list[dict[str, Any]], str]],
    evidences_by_candidate: dict[UUID, list[EvidenceItem]],
    must_req_ids: set[UUID],
) -> list[ShortlistEntry]:
    """
    Ranks candidates using deterministic tiebreak:
    1. Higher fit_score
    2. More MET must-reqs
    3. Higher mean strength across must-reqs
    4. More recent evidence (latest last_used date)
    5. Candidate_id ascending
    """
    def sort_key(item):
        cand_id, fit, conf, matches, flags, gaps, rat = item
        must_matches = [m for m in matches if m.requirement_id in must_req_ids]
        met_must_count = sum(1 for m in must_matches if m.status == "MET")
        mean_strength = (sum(m.strength for m in must_matches) / len(must_matches)) if must_matches else 0.0
        
        c_evidences = evidences_by_candidate.get(cand_id, [])
        dates = [e.last_used for e in c_evidences if e.last_used is not None]
        latest_date = max(dates) if dates else date(1900, 1, 1)
        
        # We sort descending on fit, met_must_count, mean_strength, latest_date; ascending on str(cand_id)
        return (-fit, -met_must_count, -mean_strength, latest_date, str(cand_id))

    sorted_items = sorted(candidates_data, key=sort_key)
    
    entries: list[ShortlistEntry] = []
    for rank, (cand_id, fit, conf, matches, flags, gaps, rat) in enumerate(sorted_items, start=1):
        entries.append(ShortlistEntry(
            rank=rank,
            candidate_id=cand_id,
            fit_score=fit,
            confidence=conf,
            matches=matches,
            noise_flags=flags,
            gaps=gaps,
            rationale=rat
        ))
        
    return entries
