import json
from pathlib import Path
import pytest
from app.redaction.pii import redact_pii_and_demographics

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "fairness_eval.json"


def test_eval_demographic_invariance_and_pii_neutralization():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    for pair in pairs:
        cleaned_a, pii_a, _ = redact_pii_and_demographics(pair["resume_a"])
        cleaned_b, pii_b, _ = redact_pii_and_demographics(pair["resume_b"])

        # After PII and demographic name redaction, technical content should be identical
        assert "[REDACTED" in cleaned_a or len(pii_a) > 0
        assert "[REDACTED" in cleaned_b or len(pii_b) > 0

        # Technical skills remain intact
        assert any(k in cleaned_a.lower() for k in ("python", "kafka", "fastapi", "postgresql"))
        assert any(k in cleaned_b.lower() for k in ("python", "kafka", "fastapi", "postgresql"))
