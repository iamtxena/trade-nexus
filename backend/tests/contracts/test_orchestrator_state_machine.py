"""Contract checks for orchestrator deterministic state transitions."""

from __future__ import annotations

import pytest

from src.platform_api.services.orchestrator_state_machine import (
    ALLOWED_ORCHESTRATOR_TRANSITIONS,
    INITIAL_ORCHESTRATOR_STATE,
    TERMINAL_ORCHESTRATOR_STATES,
    VALID_ORCHESTRATOR_STATES,
    OrchestratorTransitionError,
    can_transition,
    is_valid_orchestrator_state,
    transition_state,
)


def test_orchestrator_state_set_matches_gate4_contract() -> None:
    assert VALID_ORCHESTRATOR_STATES == {
        "received",
        "queued",
        "executing",
        "awaiting_tool",
        "awaiting_user_confirmation",
        "completed",
        "failed",
        "cancelled",
    }


def test_initial_state_and_state_validation_contract() -> None:
    assert INITIAL_ORCHESTRATOR_STATE == "received"
    assert is_valid_orchestrator_state("queued")
    assert not is_valid_orchestrator_state("unknown")


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("received", "queued"),
        ("queued", "executing"),
        ("executing", "awaiting_tool"),
        ("awaiting_tool", "executing"),
        ("executing", "awaiting_user_confirmation"),
        ("awaiting_user_confirmation", "executing"),
        ("executing", "completed"),
        ("executing", "failed"),
        ("executing", "cancelled"),
    ],
)
def test_valid_transitions_succeed(current: str, target: str) -> None:
    assert can_transition(current, target)
    assert transition_state(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("received", "executing"),
        ("queued", "awaiting_tool"),
        ("awaiting_tool", "completed"),
        ("awaiting_user_confirmation", "completed"),
        ("completed", "executing"),
        ("failed", "queued"),
        ("cancelled", "executing"),
    ],
)
def test_invalid_transitions_fail(current: str, target: str) -> None:
    assert not can_transition(current, target)
    with pytest.raises(OrchestratorTransitionError):
        transition_state(current, target)


@pytest.mark.parametrize("terminal_state", sorted(TERMINAL_ORCHESTRATOR_STATES))
def test_terminal_states_are_immutable(terminal_state: str) -> None:
    allowed_targets = ALLOWED_ORCHESTRATOR_TRANSITIONS[terminal_state]
    assert allowed_targets == {terminal_state}
    assert transition_state(terminal_state, terminal_state) == terminal_state
