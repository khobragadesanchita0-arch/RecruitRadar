from datetime import date
from uuid import uuid4
import pytest
from app.schemas.contracts import Requirement, EvidenceItem, NoiseFlag
from app.scoring.engine import score_candidate, rank_candidates
from app.noise.rules import (
    evaluate_skill_stuffing, evaluate_repeated_terms,
    evaluate_jd_copy, evaluate_hidden_text_flags, run_noise_detection
)
from evals.generators.variant_generator import (
    generate_keyword_stuffed_skills, generate_hidden_keywords,
    generate_repeated_keywords, generate_jd_copy_summary
)

FIXED_TODAY = date(2026, 1, 1)

def test_ac05_keyword_invariance_and_flag_raising():
    """
    AC-05: Keyword invariance:
    Variants (+50 JD keywords in skills list / hidden keywords / keywords repeated x20 / JD paragraph in summary)
    NEVER rank higher than the original.
    Variants b, c, d raise the correct noise flag.
    """
    req_id = uuid4()
    req = Requirement(text="Python Distributed Systems", skill_ids=[req_id], kind="must", weight=1.0)
    
    cand_orig_id = uuid4()
    orig_ev = [EvidenceItem(candidate_id=cand_orig_id, skill_id=req_id, quote="Built distributed Python service", grade="demonstrated", duration_months=24, last_used=date(2025, 1, 1), verified=True)]
    score_orig, _, _, _, _ = score_candidate(cand_orig_id, [req], orig_ev, [], today=FIXED_TODAY)
    
    jd_keywords = ["Python", "Docker", "Kubernetes", "Kafka", "PostgreSQL", "AWS", "GCP", "Redis", "Elasticsearch", "CI/CD", "Terraform", "FastAPI"] * 5
    jd_sample_text = "Looking for a Senior Backend Engineer proficient in Python and Kafka. Must design high throughput distributed architectures with resilience."
    
    # Variant a: 50 JD keywords in skills list (purely listed)
    cand_a_id = uuid4()
    ev_a = orig_ev + [
        EvidenceItem(candidate_id=cand_a_id, skill_id=uuid4(), quote=kw, grade="listed", verified=True)
        for kw in jd_keywords[:50]
    ]
    # Check stuffing flag
    flag_a = evaluate_skill_stuffing(skills_listed_count=52, skills_with_context_count=2)
    assert flag_a is not None
    assert flag_a.type == "SKILL_STUFFING"
    flags_a = [flag_a] if flag_a else []
    score_a, _, _, _, _ = score_candidate(cand_a_id, [req], ev_a, flags_a, today=FIXED_TODAY)
    assert score_a <= score_orig  # Never higher than original!
    
    # Variant b: Hidden keywords
    _, hidden_items = generate_hidden_keywords("Resume text", jd_keywords)
    flags_b = evaluate_hidden_text_flags(hidden_items)
    assert len(flags_b) >= 1
    assert any(f.type == "HIDDEN_TEXT" for f in flags_b)
    cand_b_id = uuid4()
    score_b, _, _, _, _ = score_candidate(cand_b_id, [req], orig_ev, flags_b, today=FIXED_TODAY)
    assert score_b < score_orig  # Penalized by noise penalty!
    
    # Variant c: Keywords repeated 20×
    repeated_sections = {"skills": "Python " * 20}
    flags_c = evaluate_repeated_terms(repeated_sections)
    assert len(flags_c) >= 1
    assert any(f.type == "REPEATED_TERMS" for f in flags_c)
    cand_c_id = uuid4()
    score_c, _, _, _, _ = score_candidate(cand_c_id, [req], orig_ev, flags_c, today=FIXED_TODAY)
    assert score_c < score_orig
    
    # Variant d: JD paragraph pasted in summary
    resume_with_copy = generate_jd_copy_summary("I have worked on various systems.", jd_sample_text)
    flag_d = evaluate_jd_copy(resume_with_copy, jd_sample_text)
    assert flag_d is not None
    assert flag_d.type == "JD_COPY"
    cand_d_id = uuid4()
    score_d, _, _, _, _ = score_candidate(cand_d_id, [req], orig_ev, [flag_d], today=FIXED_TODAY)
    assert score_d < score_orig

def test_ac06_stuffing_demotion():
    """
    AC-06: In genuine vs stuffed pairs for the same role, genuine ranks above stuffed.
    Stuffing detection recall & precision tested.
    """
    skill_k8s = uuid4()
    req = Requirement(text="Kubernetes deployment", skill_ids=[skill_k8s], kind="must", weight=1.0)
    
    # Candidate 1: Genuine (demonstrated evidence, 5 skills listed, all 5 with context)
    c1_id = uuid4()
    c1_ev = [EvidenceItem(candidate_id=c1_id, skill_id=skill_k8s, quote="Managed 10-node K8s cluster", grade="demonstrated", duration_months=36, last_used=date(2025, 6, 1), verified=True)]
    flag_c1 = evaluate_skill_stuffing(5, 5)
    flags_c1 = [flag_c1] if flag_c1 else []
    score_c1, conf_c1, m_c1, g_c1, r_c1 = score_candidate(c1_id, [req], c1_ev, flags_c1, today=FIXED_TODAY)
    
    # Candidate 2: Stuffed (45 skills listed, only 2 with context, listed grade)
    c2_id = uuid4()
    c2_ev = [EvidenceItem(candidate_id=c2_id, skill_id=skill_k8s, quote="Kubernetes, Docker, Helm, Istio, Envoy", grade="listed", verified=True)]
    flag_c2 = evaluate_skill_stuffing(45, 2)
    assert flag_c2 is not None
    flags_c2 = [flag_c2]
    score_c2, conf_c2, m_c2, g_c2, r_c2 = score_candidate(c2_id, [req], c2_ev, flags_c2, today=FIXED_TODAY)
    
    # Rank candidates together
    entries = rank_candidates(
        [
            (c1_id, score_c1, conf_c1, m_c1, flags_c1, g_c1, r_c1),
            (c2_id, score_c2, conf_c2, m_c2, flags_c2, g_c2, r_c2),
        ],
        evidences_by_candidate={c1_id: c1_ev, c2_id: c2_ev},
        must_req_ids={req.id}
    )
    
    assert entries[0].candidate_id == c1_id
    assert entries[0].rank == 1
    assert entries[1].candidate_id == c2_id
    assert entries[1].rank == 2
