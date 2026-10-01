# Scoring Configuration constants - versioned
SCORING_CONFIG_VERSION = "2.0.0"

GRADE_WEIGHT = {
    "listed": 0.0,
    "contextual": 0.4,
    "demonstrated": 0.7,
    "outcome_backed": 1.0,
}

HALF_LIFE_MONTHS = 48.0
MUST_SHARE = 0.85
NICE_SHARE = 0.15

NOISE_PEN = {
    "LOW": 0.05,
    "MED": 0.15,
    "HIGH": 0.40,
}
NOISE_PEN_CAP = 0.40
INJECTION_SCORE_CAP = 40

# Status thresholds
MET_THRESHOLD = 0.65
PARTIAL_THRESHOLD = 0.25
PARSE_CONFIDENCE_UNCERTAIN = 0.60

# Confidence weighting constants
CONFIDENCE_PARSE_WEIGHT = 0.35
CONFIDENCE_COVERAGE_WEIGHT = 0.35
CONFIDENCE_UNCERTAIN_WEIGHT = 0.20
CONFIDENCE_VERIFIER_WEIGHT = 0.10
