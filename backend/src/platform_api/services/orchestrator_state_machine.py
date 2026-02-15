"""Deterministic orchestrator state machine contract for AG-ORCH-01."""

from __future__ import annotations

OrchestratorState = str

INITIAL_ORCHESTRATOR_STATE: OrchestratorState = "received"

VALID_ORCHESTRATOR_STATES: set[OrchestratorState] = {
    "received",
    "queued",
    "executing",
    "awaiting_tool",
    "awaiting_user_confirmation",
    "completed",
    "failed",
    "cancelled",
}

TERMINAL_ORCHESTRATOR_STATES: set[OrchestratorState] = {
    "completed",
    "failed",
    "cancelled",
}

ALLOWED_ORCHESTRATOR_TRANSITIONS: dict[OrchestratorState, set[OrchestratorState]] = {
    "received": {"received", "queued", "failed", "cancelled"},
    "queued": {"queued", "executing", "failed", "cancelled"},
    "executing": {
        "executing",
        "awaiting_tool",
        "awaiting_user_confirmation",
        "completed",
        "failed",
        "cancelled",
    },
    "awaiting_tool": {"awaiting_tool", "executing", "failed", "cancelled"},
    "awaiting_user_confirmation": {
        "awaiting_user_confirmation",
        "executing",
        "failed",
        "cancelled",
    },
    "completed": {"completed"},
    "failed": {"failed"},
    "cancelled": {"cancelled"},
}


class OrchestratorTransitionError(ValueError):
    """Raised when an orchestrator state transition violates the contract."""


def is_valid_orchestrator_state(state: str) -> bool:
    return state in VALID_ORCHESTRATOR_STATES


def can_transition(current: OrchestratorState, target: OrchestratorState) -> bool:
    if current not in VALID_ORCHESTRATOR_STATES:
        return False
    if target not in VALID_ORCHESTRATOR_STATES:
        return False
    return target in ALLOWED_ORCHESTRATOR_TRANSITIONS[current]


def transition_state(current: OrchestratorState, target: OrchestratorState) -> OrchestratorState:
    if not can_transition(current, target):
        raise OrchestratorTransitionError(
            f"Invalid orchestrator transition: {current} -> {target}",
        )
    return target
