import uuid
from datetime import datetime, timezone, date
from typing import Any, Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, LargeBinary,
    Date, DateTime, ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    status = Column(String(50), default="active", nullable=False)
    failed_logins = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    memberships = relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    retention_days = Column(Integer, default=180, nullable=False)
    blind_mode_default = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    roles = relationship("Role", back_populates="workspace", cascade="all, delete-orphan")

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="recruiter", nullable=False)  # owner, admin, recruiter, hiring_manager, viewer
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")

class Role(Base):
    __tablename__ = "roles"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    jd_text = Column(Text, nullable=False)
    jd_version = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="active", nullable=False)  # draft, active, closed
    requirements_confirmed_version = Column(Integer, nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="roles")
    requirements = relationship("Requirement", back_populates="role", cascade="all, delete-orphan")
    candidates = relationship("Candidate", back_populates="role", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="role", cascade="all, delete-orphan")

class Requirement(Base):
    __tablename__ = "requirements"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    jd_version = Column(Integer, default=1, nullable=False)
    text = Column(Text, nullable=False)
    skill_ids = Column(JSON, default=list, nullable=False)  # list of skill UUID strings
    kind = Column(String(20), nullable=False)  # must, nice
    weight = Column(Float, default=1.0, nullable=False)
    min_months = Column(Integer, nullable=True)
    source_span = Column(JSON, nullable=True)  # [start, end]
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    role = relationship("Role", back_populates="requirements")

class Skill(Base):
    __tablename__ = "skills"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    canonical_name = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(100), nullable=True)
    parent_skill_id = Column(String(36), ForeignKey("skills.id"), nullable=True)
    embedding = Column(JSON, nullable=True)  # vector representation as float list
    release_year = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    aliases = relationship("SkillAlias", back_populates="skill", cascade="all, delete-orphan")

class SkillAlias(Base):
    __tablename__ = "skill_aliases"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    skill = relationship("Skill", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("alias", "skill_id", name="uq_skill_alias"),
    )

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    display_alias = Column(String(100), nullable=False)  # e.g. "Candidate #A17"
    pii_encrypted = Column(LargeBinary, nullable=True)
    status = Column(String(50), default="new", nullable=False)  # new, shortlisted, hold, not_progressing, withdrawn
    dedupe_hash = Column(String(64), nullable=True, index=True)
    retention_until = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    role = relationship("Role", back_populates="candidates")
    files = relationship("FileRecord", back_populates="candidate", cascade="all, delete-orphan")
    profile = relationship("CandidateProfile", uselist=False, back_populates="candidate", cascade="all, delete-orphan")
    evidence_items = relationship("EvidenceItem", back_populates="candidate", cascade="all, delete-orphan")

class FileRecord(Base):
    __tablename__ = "files"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True)
    storage_key = Column(String(500), nullable=False)
    filename = Column(String(255), nullable=False)
    mime = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    scan_status = Column(String(50), default="pending", nullable=False)  # pending, clean, infected, failed
    parse_status = Column(String(50), default="pending", nullable=False)  # pending, parsed, needs_attention, failed
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    candidate = relationship("Candidate", back_populates="files")

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    parsed = Column(JSON, default=dict, nullable=False)
    analysis_text = Column(Text, nullable=False)
    hidden_text_flags = Column(JSON, default=list, nullable=False)
    parse_confidence = Column(Float, default=1.0, nullable=False)
    parser_version = Column(String(50), default="1.0.0", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    candidate = relationship("Candidate", back_populates="profile")

class Run(Base):
    __tablename__ = "runs"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    state = Column(String(50), default="CREATED", nullable=False, index=True)
    params = Column(JSON, default=dict, nullable=False)
    plan = Column(JSON, default=dict, nullable=False)
    budget = Column(JSON, default=dict, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    prompt_versions = Column(JSON, default=dict, nullable=False)
    model_versions = Column(JSON, default=dict, nullable=False)
    scoring_config_version = Column(String(50), default="2.0.0", nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    role = relationship("Role", back_populates="runs")
    shortlist_entries = relationship("ShortlistEntry", back_populates="run", cascade="all, delete-orphan")
    match_results = relationship("MatchResult", back_populates="run", cascade="all, delete-orphan")
    noise_reports = relationship("NoiseReport", back_populates="run", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_task_id = Column(String(36), nullable=True)
    type = Column(String(50), nullable=False)
    state = Column(String(50), default="PENDING", nullable=False)
    checkpoint = Column(JSON, default=dict, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class TaskStep(Base):
    __tablename__ = "task_steps"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    seq = Column(Integer, default=0, nullable=False)
    agent = Column(String(50), nullable=False)
    candidate_id = Column(String(36), nullable=True)
    state = Column(String(50), default="PENDING", nullable=False)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    input_ref = Column(JSON, nullable=True)
    output_ref = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True)
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    quote = Column(Text, nullable=False)
    span_start = Column(Integer, default=0, nullable=False)
    span_end = Column(Integer, default=0, nullable=False)
    grade = Column(String(50), nullable=False)  # listed, contextual, demonstrated, outcome_backed
    role_ref = Column(String(255), nullable=True)
    duration_months = Column(Integer, nullable=True)
    last_used = Column(Date, nullable=True)
    outcome_text = Column(Text, nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    candidate = relationship("Candidate", back_populates="evidence_items")

class MatchResult(Base):
    __tablename__ = "match_results"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # MET, PARTIAL, UNCERTAIN, MISSING
    strength = Column(Float, default=0.0, nullable=False)
    evidence_ids = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    run = relationship("Run", back_populates="match_results")

    __table_args__ = (
        UniqueConstraint("run_id", "candidate_id", "requirement_id", name="uq_run_candidate_req"),
    )

class NoiseReport(Base):
    __tablename__ = "noise_reports"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    flags = Column(JSON, default=list, nullable=False)
    dismissed = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    run = relationship("Run", back_populates="noise_reports")

    __table_args__ = (
        UniqueConstraint("run_id", "candidate_id", name="uq_run_candidate_noise"),
    )

class ShortlistEntry(Base):
    __tablename__ = "shortlist_entries"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    fit_score = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    rationale = Column(String(500), nullable=False)
    gaps = Column(JSON, default=list, nullable=False)
    override_rank = Column(Integer, nullable=True)
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    run = relationship("Run", back_populates="shortlist_entries")

class InterviewKit(Base):
    __tablename__ = "interview_kits"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    questions = Column(JSON, default=list, nullable=False)
    rubric = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    run_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

class ToolDef(Base):
    __tablename__ = "tools"
    name = Column(String(100), primary_key=True)
    version = Column(String(50), nullable=False)
    description = Column(Text, default="", nullable=False)
    schemas = Column(JSON, default=dict, nullable=False)
    permissions = Column(JSON, default=list, nullable=False)
    risk_level = Column(String(20), default="LOW", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class ToolExecution(Base):
    __tablename__ = "tool_executions"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_step_id = Column(String(36), nullable=True, index=True)
    tool_id = Column(String(100), ForeignKey("tools.name"), nullable=False)
    status = Column(String(50), nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    input_redacted = Column(JSON, default=dict, nullable=False)
    output_redacted = Column(JSON, default=dict, nullable=False)
    error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class Memory(Base):
    __tablename__ = "memories"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=True, index=True)
    kind = Column(String(50), nullable=False)  # preference, calibration, fact
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    importance = Column(Float, default=1.0, nullable=False)
    use_count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), nullable=False, index=True)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(100), default="shortlist_approval", nullable=False)
    risk = Column(String(20), default="HIGH", nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, approved, rejected, expired
    requested_by = Column(String(36), nullable=True)
    approver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), nullable=False, index=True)
    actor_id = Column(String(36), nullable=False)
    actor_type = Column(String(50), default="user", nullable=False)
    action = Column(String(100), nullable=False)  # overrides, dismissals, deletions, exports, auth
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(36), nullable=True)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    request_id = Column(String(100), nullable=True)
    prev_hash = Column(String(64), nullable=True)
    hash = Column(String(64), nullable=False)  # SHA-256 hash chaining
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
