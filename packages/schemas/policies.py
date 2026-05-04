from __future__ import annotations

# ============================================================
# packages/schemas/policies.py
#
# AI INSTRUCTION: DO NOT implement blocking/firewall logic here.
# This file defines the *data schemas* only.  The actual enforcement
# engine lives in apps/backend/src/services/firewall.py and is
# explicitly deferred until after Phase 1 is complete.
# ============================================================

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PolicyAction(str, Enum):
    """What the firewall should do when a policy matches."""
    ALLOW = "allow"
    BLOCK = "block"
    ALERT = "alert"     # log + notify, do not block
    RATE_LIMIT = "rate_limit"


class PolicyScope(str, Enum):
    NETWORK = "network"      # applies to NetworkIntercept events
    TERMINAL = "terminal"    # applies to TerminalAction events
    BOTH = "both"


class PolicyRule(BaseModel):
    """
    A single policy rule.  Rules are evaluated in priority order (lower
    number = higher priority).  The first matching rule wins.
    """
    id: str = Field(..., description="Unique rule identifier, e.g. 'block-rm-rf'")
    priority: int = Field(default=100, ge=0, description="Lower = evaluated first")
    enabled: bool = Field(default=True)
    scope: PolicyScope = Field(default=PolicyScope.BOTH)
    description: str = Field(default="")

    # --- Match conditions (all present conditions must match) ---
    # For NETWORK scope
    url_pattern: Optional[str] = Field(
        default=None,
        description="Regex applied to the request URL",
    )
    method: Optional[str] = Field(
        default=None,
        description="HTTP method to match, e.g. 'POST'",
    )
    # For TERMINAL scope
    command_pattern: Optional[str] = Field(
        default=None,
        description="Regex applied to the command_executed field",
    )
    user_pattern: Optional[str] = Field(
        default=None,
        description="Regex applied to the OS username",
    )
    # Shared
    source_process_pattern: Optional[str] = Field(
        default=None,
        description="Regex applied to source_process",
    )

    # --- Action ---
    action: PolicyAction = Field(default=PolicyAction.ALERT)
    alert_message: Optional[str] = Field(
        default=None,
        description="Human-readable message emitted when this rule fires",
    )

    model_config = {"extra": "forbid"}


class PolicySet(BaseModel):
    """A named collection of PolicyRule objects loaded from YAML/JSON config."""
    name: str = Field(..., description="Human-readable name for this policy set")
    version: str = Field(default="1.0.0")
    rules: list[PolicyRule] = Field(default_factory=list)

    model_config = {"extra": "allow"}
