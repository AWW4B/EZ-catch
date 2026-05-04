from __future__ import annotations

# ============================================================
# apps/backend/src/services/evaluator.py
#
# AI INSTRUCTION: Phase 2+ feature.
# This service will score / classify intercepted events against
# a loaded PolicySet to decide whether to ALLOW, ALERT, or
# BLOCK.  Do NOT implement blocking logic here yet — see Rule #2
# in Plan.md.  Stub is provided so imports do not fail.
# ============================================================

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from packages.schemas.events import NetworkIntercept, TerminalAction
    from packages.schemas.policies import PolicyAction, PolicyRule, PolicySet

# Import for runtime use (will succeed inside Docker since packages/ is now copied)
try:
    from packages.schemas.policies import PolicyAction, PolicyRule, PolicySet
except ImportError:
    from enum import Enum
    class PolicyAction(str, Enum):  # type: ignore[no-redef]
        ALLOW = "allow"
        BLOCK = "block"
        ALERT = "alert"
        RATE_LIMIT = "rate_limit"
    PolicyRule = None  # type: ignore[assignment,misc]
    PolicySet = None   # type: ignore[assignment,misc]


class EvaluationResult:
    """Outcome of running a single event through the policy engine."""
    __slots__ = ("rule", "action", "message")

    def __init__(
        self,
        rule: Optional[PolicyRule],
        action: PolicyAction,
        message: str,
    ) -> None:
        self.rule = rule
        self.action = action
        self.message = message

    def __repr__(self) -> str:
        rule_id = self.rule.id if self.rule else "default"
        return f"<EvaluationResult rule={rule_id!r} action={self.action}>"


class PolicyEvaluator:
    """
    Evaluates events against a PolicySet.

    Currently in *monitoring-only* mode — all events are passed through
    as ALLOW.  Alerting and blocking will be wired once Phase 2 begins.
    """

    def __init__(self, policy_set: Optional[PolicySet] = None) -> None:
        self._policy_set = policy_set

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_network(self, event: "NetworkIntercept") -> EvaluationResult:
        if not self._policy_set:
            return self._default_allow()
        for rule in self._sorted_rules():
            if rule.scope.value not in ("network", "both"):
                continue
            if not rule.enabled:
                continue
            if self._matches_network(rule, event):
                return EvaluationResult(rule, rule.action, rule.alert_message or "")
        return self._default_allow()

    def evaluate_terminal(self, event: "TerminalAction") -> EvaluationResult:
        if not self._policy_set:
            return self._default_allow()
        for rule in self._sorted_rules():
            if rule.scope.value not in ("terminal", "both"):
                continue
            if not rule.enabled:
                continue
            if self._matches_terminal(rule, event):
                return EvaluationResult(rule, rule.action, rule.alert_message or "")
        return self._default_allow()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _sorted_rules(self) -> list[PolicyRule]:
        return sorted(self._policy_set.rules, key=lambda r: r.priority)

    @staticmethod
    def _default_allow() -> EvaluationResult:
        return EvaluationResult(None, PolicyAction.ALLOW, "default allow")

    @staticmethod
    def _re_match(pattern: Optional[str], value: Optional[str]) -> bool:
        if pattern is None:
            return True   # no constraint → matches everything
        if value is None:
            return False
        return bool(re.search(pattern, value, re.IGNORECASE))

    def _matches_network(self, rule: PolicyRule, event: "NetworkIntercept") -> bool:
        return (
            self._re_match(rule.url_pattern, event.url)
            and self._re_match(rule.method, event.method)
            and self._re_match(rule.source_process_pattern, event.source_process)
        )

    def _matches_terminal(self, rule: PolicyRule, event: "TerminalAction") -> bool:
        return (
            self._re_match(rule.command_pattern, event.command_executed)
            and self._re_match(rule.user_pattern, event.user)
            and self._re_match(rule.source_process_pattern, event.source_process)
        )
