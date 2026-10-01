import json
from pathlib import Path
import pytest
from app.noise.rules import run_noise_detection

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "stuffing_eval.json"


def test_eval_stuffing_detection_on_benchmarks():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        flags = run_noise_detection(
            resume_text=" ".join(case["skills_listed"]),
            jd_text="Python and backend systems.",
            section_texts={"skills": " ".join(case["skills_listed"])},
            skills_listed_count=len(case["skills_listed"]),
            skills_with_context_count=len(case["skills_with_context"]),
            hidden_text_items=[],
            evidences=[],
            skills_map={},
        )
        stuffing_flags = [f for f in flags if f.type == "SKILL_STUFFING"]
        assert len(stuffing_flags) >= 1, f"Failed for {case['id']}: expected SKILL_STUFFING flag"
        flag = stuffing_flags[0]
        assert flag.severity == case["expected_severity"], f"Severity mismatch for {case['id']}"
