"""Deterministic orchestrator retry and failure-budget controls (AG-ORCH-03)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryBudgetPolicy:
    max_attempts: int = 3
    max_failures: int = 3
    base_backoff_seconds: int = 1
    max_backoff_seconds: int = 30


@dataclass
class RetryRuntimeState:
    attempts: int = 0
    failures: int = 0
    terminal: bool = False


@dataclass(frozen=True)
class RetryDecision:
    retry_allowed: bool
    terminal: bool
    next_state: str
    reason: str
    retry_after_seconds: int | None
    attempts: int
    failures: int
    remaining_attempts: int
    remaining_failures: int


class OrchestratorRetryPolicyService:
    """Tracks attempts/failures and emits deterministic bounded retry decisions."""

    def __init__(self, *, policy: RetryBudgetPolicy | None = None) -> None:
        self._policy = policy or RetryBudgetPolicy()
        self._state_by_item: dict[str, RetryRuntimeState] = {}

    def begin_attempt(self, *, item_id: str) -> RetryRuntimeState:
        state = self._state_for(item_id)
        if state.terminal:
            raise ValueError(f"Retry state is terminal for item: {item_id}")
        state.attempts += 1
        return state

    def record_failure(self, *, item_id: str) -> RetryDecision:
        state = self._state_for(item_id)
        if state.terminal:
            return self._terminal_decision(state=state, reason="failure_budget_exhausted")
        if state.attempts == 0:
            state.attempts = 1
        state.failures += 1

        attempts_exhausted = state.attempts >= self._policy.max_attempts
        failures_exhausted = state.failures >= self._policy.max_failures
        if attempts_exhausted or failures_exhausted:
            state.terminal = True
            reason = "attempt_budget_exhausted" if attempts_exhausted else "failure_budget_exhausted"
            return self._terminal_decision(state=state, reason=reason)

        retry_after_seconds = min(
            self._policy.base_backoff_seconds * (2 ** max(state.failures - 1, 0)),
            self._policy.max_backoff_seconds,
        )
        return RetryDecision(
            retry_allowed=True,
            terminal=False,
            next_state="awaiting_tool",
            reason="retry_scheduled",
            retry_after_seconds=retry_after_seconds,
            attempts=state.attempts,
            failures=state.failures,
            remaining_attempts=max(self._policy.max_attempts - state.attempts, 0),
            remaining_failures=max(self._policy.max_failures - state.failures, 0),
        )

    def record_success(self, *, item_id: str) -> RetryRuntimeState:
        state = self._state_for(item_id)
        state.terminal = True
        return state

    def snapshot(self, *, item_id: str) -> RetryRuntimeState:
        state = self._state_for(item_id)
        return RetryRuntimeState(
            attempts=state.attempts,
            failures=state.failures,
            terminal=state.terminal,
        )

    def _state_for(self, item_id: str) -> RetryRuntimeState:
        state = self._state_by_item.get(item_id)
        if state is None:
            state = RetryRuntimeState()
            self._state_by_item[item_id] = state
        return state

    def _terminal_decision(self, *, state: RetryRuntimeState, reason: str) -> RetryDecision:
        return RetryDecision(
            retry_allowed=False,
            terminal=True,
            next_state="failed",
            reason=reason,
            retry_after_seconds=None,
            attempts=state.attempts,
            failures=state.failures,
            remaining_attempts=max(self._policy.max_attempts - state.attempts, 0),
            remaining_failures=max(self._policy.max_failures - state.failures, 0),
        )


__all__ = [
    "OrchestratorRetryPolicyService",
    "RetryBudgetPolicy",
    "RetryDecision",
    "RetryRuntimeState",
]
