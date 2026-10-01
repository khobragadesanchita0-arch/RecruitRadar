"""Authorization actor model and permission matrix."""
from dataclasses import dataclass, field
from typing import List, Set

# Role → allowed actions map
ROLE_PERMISSIONS: dict[str, Set[str]] = {
    "owner": {
        "role:create", "role:view", "role:edit", "role:delete",
        "candidate:create", "candidate:view", "candidate:delete",
        "run:create", "run:view",
        "shortlist:view", "shortlist:reorder", "shortlist:dismiss_flag",
        "interview_kit:view",
        "approval:create", "approval:view", "approval:decide",
        "audit:view",
    },
    "admin": {
        "role:create", "role:view", "role:edit", "role:delete",
        "candidate:create", "candidate:view", "candidate:delete",
        "run:create", "run:view",
        "shortlist:view", "shortlist:reorder", "shortlist:dismiss_flag",
        "interview_kit:view",
        "approval:create", "approval:view", "approval:decide",
        "audit:view",
    },
    "recruiter": {
        "role:create", "role:view", "role:edit",
        "candidate:create", "candidate:view",
        "run:create", "run:view",
        "shortlist:view", "shortlist:reorder", "shortlist:dismiss_flag",
        "interview_kit:view",
        "approval:create", "approval:view",
    },
    "hiring_manager": {
        "role:view",
        "candidate:view",
        "run:view",
        "shortlist:view",
        "interview_kit:view",
        "approval:view", "approval:decide",
    },
    "viewer": {
        "role:view",
        "candidate:view",
        "run:view",
        "shortlist:view",
    },
}


@dataclass
class Actor:
    user_id: str
    workspace_id: str
    tenant_id: str
    role: str = "viewer"
    is_admin: bool = False
    permissions: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if self.role in ("admin", "owner"):
            self.is_admin = True
        if not self.permissions:
            self.permissions = ROLE_PERMISSIONS.get(self.role, set())
        if self.is_admin:
            self.permissions = ROLE_PERMISSIONS.get("admin", set())

    def can(self, action: str) -> bool:
        return action in self.permissions

    def require(self, action: str):
        from app.core.errors import ForbiddenError
        if not self.can(action):
            raise ForbiddenError(action)
