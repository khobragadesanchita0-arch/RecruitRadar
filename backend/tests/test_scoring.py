from datetime import date
from uuid import uuid4
import pytest
from app.schemas.contracts import Requirement, EvidenceItem, NoiseFlag
from app.scoring.engine import (
    score_candidate, compute_requirement_strength, rank_candidates
)

FIXED_TODAY = date(2026, 1, 1)

def test_t1_only_listed_evidence():
    """T1: One must-req (Kafka). Evidence: only 'listed' -> strength 0.0 -> status UNCERTAIN; fit 0"""
    kafka_id = uuid4()
    req = Requirement(
        text="3+ years Kafka experience",
        skill_ids=[kafka_id],
        kind="must",
        weight=1.0,
        min_months=36
    )
    cand_id = uuid4()
    evidence = EvidenceItem(
        candidate_id=cand_id,
        skill_id=kafka_id,
        quote="Kafka, Redis, Python",
        grade="listed",
        verified=True
    )
    
    fit_score, confidence, matches, gaps, _ = score_candidate(
        candidate_id=cand_id,
        requirements=[req],
        evidences=[evidence],
        noise_flags=[],
        today=FIXED_TODAY,
    )
    
    assert len(matches) == 1
    assert matches[0].strength == 0.0
    assert matches[0].status == "UNCERTAIN"
    assert fit_score == 0

def test_t2_repeated_listed_evidence():
    """T2: Same evidence repeated 20× -> identical result to T1"""
    kafka_id = uuid4()
    req = Requirement(
        text="Kafka",
        skill_ids=[kafka_id],
        kind="must",
        weight=1.0,
        min_months=36
    )
    cand_id = uuid4()
    evidences = [
        EvidenceItem(
            candidate_id=cand_id,
            skill_id=kafka_id,
            quote="Kafka",
            grade="listed",
            verified=True
        )
        for _ in range(20)
    ]
    
    fit_score, confidence, matches, gaps, _ = score_candidate(
        candidate_id=cand_id,
        requirements=[req],
        evidences=evidences,
        noise_flags=[],
        today=FIXED_TODAY,
    )
    
    assert matches[0].strength == 0.0
    assert matches[0].status == "UNCERTAIN"
    assert fit_score == 0

def test_t3_multi_requirement_demonstrated_and_outcome():
    """
    T3: Must-reqs: Kafka w=0.4 (min 24 mo), PostgreSQL w=0.6 (min 36 mo).
    Kafka: demonstrated, last used 12 mo ago, 30 mo duration.
    PostgreSQL: outcome_backed, last used 0 mo, 48 mo duration.
    Kafka strength ≈ 0.5886 (PARTIAL); Postgres strength 1.0 (MET); must_score ≈ 0.8354; fit_score = 84
    """
    kafka_id = uuid4()
    postgres_id = uuid4()
    
    req_kafka = Requirement(
        text="Kafka",
        skill_ids=[kafka_id],
        kind="must",
        weight=0.4,
        min_months=24
    )
    req_pg = Requirement(
        text="PostgreSQL",
        skill_ids=[postgres_id],
        kind="must",
        weight=0.6,
        min_months=36
    )
    
    cand_id = uuid4()
    # 12 months before FIXED_TODAY (2026-01-01) is 2025-01-01
    ev_kafka = EvidenceItem(
        candidate_id=cand_id,
        skill_id=kafka_id,
        quote="Built Kafka consumers in Python processing 40k msg/s",
        grade="demonstrated",
        duration_months=30,
        last_used=date(2025, 1, 1),
        verified=True
    )
    # 0 months before FIXED_TODAY is 2026-01-01
    ev_pg = EvidenceItem(
        candidate_id=cand_id,
        skill_id=postgres_id,
        quote="Tuned PostgreSQL indexes reducing latency by 45%",
        grade="outcome_backed",
        duration_months=48,
        last_used=date(2026, 1, 1),
        verified=True
    )
    
    fit_score, confidence, matches, gaps, _ = score_candidate(
        candidate_id=cand_id,
        requirements=[req_kafka, req_pg],
        evidences=[ev_kafka, ev_pg],
        noise_flags=[],
        today=FIXED_TODAY,
    )
    
    match_k = next(m for m in matches if m.requirement_id == req_kafka.id)
    match_pg = next(m for m in matches if m.requirement_id == req_pg.id)
    
    assert abs(match_k.strength - 0.5886) < 0.001
    assert match_k.status == "PARTIAL"
    assert abs(match_pg.strength - 1.0) < 0.001
    assert match_pg.status == "MET"
    assert fit_score == 84

def test_t4_low_noise_flag():
    """T4: T3 plus one LOW noise flag -> fit = round(100*0.8354*0.95) = 79"""
    kafka_id = uuid4()
    postgres_id = uuid4()
    req_kafka = Requirement(text="Kafka", skill_ids=[kafka_id], kind="must", weight=0.4, min_months=24)
    req_pg = Requirement(text="PostgreSQL", skill_ids=[postgres_id], kind="must", weight=0.6, min_months=36)
    
    cand_id = uuid4()
    ev_kafka = EvidenceItem(candidate_id=cand_id, skill_id=kafka_id, quote="q", grade="demonstrated", duration_months=30, last_used=date(2025, 1, 1), verified=True)
    ev_pg = EvidenceItem(candidate_id=cand_id, skill_id=postgres_id, quote="q", grade="outcome_backed", duration_months=48, last_used=date(2026, 1, 1), verified=True)
    
    flag = NoiseFlag(type="REPEATED_TERMS", severity="LOW", detail="minor repetition")
    
    fit_score, _, _, _, _ = score_candidate(
        candidate_id=cand_id,
        requirements=[req_kafka, req_pg],
        evidences=[ev_kafka, ev_pg],
        noise_flags=[flag],
        today=FIXED_TODAY,
    )
    assert fit_score == 79

def test_t5_noise_penalty_capped():
    """T5: T3 plus MED+HIGH flags -> noise_pen capped at 0.40 -> fit = round(100*0.8354*0.60) = 50"""
    kafka_id = uuid4()
    postgres_id = uuid4()
    req_kafka = Requirement(text="Kafka", skill_ids=[kafka_id], kind="must", weight=0.4, min_months=24)
    req_pg = Requirement(text="PostgreSQL", skill_ids=[postgres_id], kind="must", weight=0.6, min_months=36)
    
    cand_id = uuid4()
    ev_kafka = EvidenceItem(candidate_id=cand_id, skill_id=kafka_id, quote="q", grade="demonstrated", duration_months=30, last_used=date(2025, 1, 1), verified=True)
    ev_pg = EvidenceItem(candidate_id=cand_id, skill_id=postgres_id, quote="q", grade="outcome_backed", duration_months=48, last_used=date(2026, 1, 1), verified=True)
    
    flags = [
        NoiseFlag(type="SKILL_STUFFING", severity="MED", detail="stuffed skills"),
        NoiseFlag(type="JD_COPY", severity="HIGH", detail="copied jd text"),
    ]
    
    fit_score, _, _, _, _ = score_candidate(
        candidate_id=cand_id,
        requirements=[req_kafka, req_pg],
        evidences=[ev_kafka, ev_pg],
        noise_flags=flags,
        today=FIXED_TODAY,
    )
    assert fit_score == 50

def test_t6_prompt_injection_cap():
    """T6: T3 plus PROMPT_INJECTION (HIGH) -> fit = min(50, 40) = 40"""
    kafka_id = uuid4()
    postgres_id = uuid4()
    req_kafka = Requirement(text="Kafka", skill_ids=[kafka_id], kind="must", weight=0.4, min_months=24)
    req_pg = Requirement(text="PostgreSQL", skill_ids=[postgres_id], kind="must", weight=0.6, min_months=36)
    
    cand_id = uuid4()
    ev_kafka = EvidenceItem(candidate_id=cand_id, skill_id=kafka_id, quote="q", grade="demonstrated", duration_months=30, last_used=date(2025, 1, 1), verified=True)
    ev_pg = EvidenceItem(candidate_id=cand_id, skill_id=postgres_id, quote="q", grade="outcome_backed", duration_months=48, last_used=date(2026, 1, 1), verified=True)
    
    flags = [
        NoiseFlag(type="PROMPT_INJECTION", severity="HIGH", detail="ignore previous instructions"),
        NoiseFlag(type="SKILL_STUFFING", severity="MED", detail="stuffed"),
    ]
    
    fit_score, _, _, _, _ = score_candidate(
        candidate_id=cand_id,
        requirements=[req_kafka, req_pg],
        evidences=[ev_kafka, ev_pg],
        noise_flags=flags,
        today=FIXED_TODAY,
    )
    assert fit_score == 40

def test_t7_diminishing_returns():
    """T7: Two evidences for one req, values 0.5 and 0.5 -> strength = 1 - 0.5*0.5 = 0.75"""
    skill_id = uuid4()
    req = Requirement(text="Python", skill_ids=[skill_id], kind="must", weight=1.0)
    cand_id = uuid4()
    
    # We construct 2 evidences that each evaluate to 0.5:
    # E.g. grade="contextual" (0.4) doesn't equal 0.5, so let's verify diminishing returns formula directly
    # value = GRADE_WEIGHT * recency * duration
    # If 2 verified items have values v1, v2: strength = 1 - (1-v1)*(1-v2)
    ev1 = EvidenceItem(candidate_id=cand_id, skill_id=skill_id, quote="q1", grade="outcome_backed", duration_months=12, last_used=date(2022, 1, 1), verified=True) # 48 mo ago -> recency = 0.5, value = 1.0 * 0.5 = 0.5
    ev2 = EvidenceItem(candidate_id=cand_id, skill_id=skill_id, quote="q2", grade="outcome_backed", duration_months=12, last_used=date(2022, 1, 1), verified=True) # 48 mo ago -> recency = 0.5, value = 1.0 * 0.5 = 0.5
    
    strength, _, _ = compute_requirement_strength(req, [ev1, ev2], today=FIXED_TODAY)
    assert abs(strength - 0.75) < 0.001

def test_t8_unverified_evidence_contributes_zero():
    """T8: Unverified evidence (verified=False) contributes 0"""
    skill_id = uuid4()
    req = Requirement(text="Docker", skill_ids=[skill_id], kind="must", weight=1.0)
    cand_id = uuid4()
    ev = EvidenceItem(candidate_id=cand_id, skill_id=skill_id, quote="q", grade="outcome_backed", verified=False)
    
    strength, _, _ = compute_requirement_strength(req, [ev], today=FIXED_TODAY)
    assert strength == 0.0

def test_t9_determinism_10x():
    """T9: Same inputs run 10× -> identical outputs"""
    kafka_id = uuid4()
    req = Requirement(text="Kafka", skill_ids=[kafka_id], kind="must", weight=1.0)
    cand_id = uuid4()
    ev = EvidenceItem(candidate_id=cand_id, skill_id=kafka_id, quote="q", grade="demonstrated", duration_months=24, last_used=date(2025, 1, 1), verified=True)
    
    first_res = score_candidate(cand_id, [req], [ev], [], today=FIXED_TODAY)
    for _ in range(9):
        curr_res = score_candidate(cand_id, [req], [ev], [], today=FIXED_TODAY)
        assert first_res[0] == curr_res[0]  # fit_score
        assert first_res[1] == curr_res[1]  # confidence
        assert first_res[2][0].strength == curr_res[2][0].strength

def test_t10_property_adding_listed_evidence_never_increases_score():
    """T10: Property test: appending 'listed' evidence for any skills never increases fit_score or improves rank"""
    k_id = uuid4()
    req = Requirement(text="Kafka", skill_ids=[k_id], kind="must", weight=1.0)
    cand_id = uuid4()
    
    base_ev = EvidenceItem(candidate_id=cand_id, skill_id=k_id, quote="q", grade="contextual", duration_months=12, last_used=date(2025, 1, 1), verified=True)
    score_before, _, _, _, _ = score_candidate(cand_id, [req], [base_ev], [], today=FIXED_TODAY)
    
    # Add 50 'listed' evidence items for various skills
    stuffed_evidences = [base_ev] + [
        EvidenceItem(candidate_id=cand_id, skill_id=uuid4(), quote=f"Skill {i}", grade="listed", verified=True)
        for i in range(50)
    ]
    # Also add 'listed' for the exact required skill
    stuffed_evidences.append(
        EvidenceItem(candidate_id=cand_id, skill_id=k_id, quote="Kafka in skills list", grade="listed", verified=True)
    )
    
    score_after, _, _, _, _ = score_candidate(cand_id, [req], stuffed_evidences, [], today=FIXED_TODAY)
    assert score_after <= score_before
