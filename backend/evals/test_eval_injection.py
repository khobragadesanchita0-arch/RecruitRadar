import json
from pathlib import Path
import pytest
from app.noise.injection_scan import scan_for_prompt_injection

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "injection_eval.json"


def test_eval_prompt_injection_detection_and_removal():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        flags, cleaned_text = scan_for_prompt_injection(case["text"])
        assert len(flags) >= 1, f"Failed for {case['id']}: expected PROMPT_INJECTION flag"
        assert flags[0].type == "PROMPT_INJECTION"
        assert flags[0].severity == "HIGH"
        # Confirm prohibited payload was removed from cleaned_text
        assert "ignore previous" not in cleaned_text.lower()
        assert "you are an" not in cleaned_text.lower()
        assert "curl " not in cleaned_text.lower()
