from datetime import date
from typing import Any, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class Requirement(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str
    skill_ids: list[UUID]              # canonical skills this requirement is about
    kind: Literal["must", "nice"]
    weight: float                      # >0; normalised within kind before scoring
    min_months: int | None = None      # e.g. 36 for "3+ years"
    source_span: tuple[int, int] | None = None

class EvidenceItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    skill_id: UUID
    quote: str                         # VERBATIM from visible resume text
    span_start: int = 0
    span_end: int = 0                  # offsets in analysis_text
    grade: Literal["listed", "contextual", "demonstrated", "outcome_backed"]
    role_ref: str | None = None        # e.g. "Backend Engineer @ Acme (2022-2025)"
    duration_months: int | None = None
    last_used: date | None = None      # None => treated as unknown (recency factor 0.5)
    outcome_text: str | None = None
    verified: bool = False             # set True only by the span verifier

class RequirementMatch(BaseModel):
    requirement_id: UUID
    status: Literal["MET", "PARTIAL", "UNCERTAIN", "MISSING"]
    strength: float                    # 0..1
    evidence_ids: list[UUID] = Field(default_factory=list)

class NoiseFlag(BaseModel):
    type: Literal[
        "SKILL_STUFFING",
        "HIDDEN_TEXT",
        "JD_COPY",
        "REPEATED_TERMS",
        "TIMELINE_ANACHRONISM",
        "PROMPT_INJECTION"
    ]
    severity: Literal["LOW", "MED", "HIGH"]
    detail: str                        # human-readable, data-derived
    metrics: dict[str, Any] = Field(default_factory=dict)
    dismissed: bool = False
    dismiss_reason: str | None = None

class ShortlistEntry(BaseModel):
    rank: int
    candidate_id: UUID
    fit_score: int                     # 0..100
    confidence: float                  # 0..1
    matches: list[RequirementMatch]
    noise_flags: list[NoiseFlag] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)  # {requirement_id, status, suggested_probe}
    rationale: str                     # <=60 words, generated from structured data only
    override_rank: int | None = None
    override_reason: str | None = None
