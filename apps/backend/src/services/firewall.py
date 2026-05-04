from __future__ import annotations

# ============================================================
# apps/backend/src/services/firewall.py
#
# AI INSTRUCTION: Phase 2+ feature.  Do NOT implement blocking
# logic yet — see Rule #2 in Plan.md.  This module is a
# deliberate stub so the import graph is complete and Phase 2
# development can begin by adding code here without restructuring.
# ============================================================


class FirewallEngine:
    """
    Placeholder for the future enforcement engine.

    In Phase 2 this class will:
    - Load PolicyRules from the DB / YAML config.
    - Instantiate a PolicyEvaluator per incoming request.
    - For BLOCK actions: terminate the proxied connection mid-flight via
      mitmproxy's ``flow.kill()`` API.
    - For RATE_LIMIT actions: delay forwarding using asyncio.sleep.
    - Emit structured alert events for ALERT actions.

    Nothing is implemented yet to comply with the monitoring-only
    mandate of Phase 1.
    """

    def __init__(self) -> None:
        self._enabled: bool = False   # Always False in Phase 1

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enforce(self, *_args, **_kwargs) -> None:
        """No-op during Phase 1."""
        return
