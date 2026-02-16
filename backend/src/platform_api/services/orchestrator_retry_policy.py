"""Deterministic orchestrator retry and failure-budget controls (AG-ORCH-03)."""

from __future__ import annotations

from dataclasses import dataclass

from src.platform_api.services.orchestrator_trace_service import (
    OrchestratorTraceIdentity,
    OrchestratorTraceService,
)
from src.platform_api.state_store import InMemoryStateStore


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

    def __init__(
        self,
        *,
        policy: RetryBudgetPolicy | None = None,
        store: InMemoryStateStore | None = None,
        trace_service: OrchestratorTraceService | None = None,
        trace_identity: OrchestratorTraceIdentity | None = None,
    ) -> None:
        self._policy = policy or RetryBudgetPolicy()
        self._state_by_item: dict[str, RetryRuntimeState] = {}
        self._trace_service = trace_service or (OrchestratorTraceService(store=store) if store is not None else None)
        self._trace_identity = trace_identity

    def begin_attempt(self, *, item_id: str) -> RetryRuntimeState:
        state = self._state_for(item_id)
        if state.terminal:
            raise ValueError(f"Retry state is terminal for item: {item_id}")
        state.attempts += 1
        self._record_trace(
            run_id=item_id,
            event="retry_attempt_started",
            step="begin_attempt",
            from_state=None,
            to_state="executing",
            metadata={
                "attempts": state.attempts,
                "failures": state.failures,
                "remainingAttempts": max(self._policy.max_attempts - state.attempts, 0),
                "remainingFailures": max(self._policy.max_failures - state.failures, 0),
            },
        )
        return state

    def record_failure(self, *, item_id: str) -> RetryDecision:
        state = self._state_for(item_id)
        if state.terminal:
            decision = self._terminal_decision(state=state, reason="failure_budget_exhausted")
            self._record_trace(
                run_id=item_id,
                event="retry_terminal_decision",
                step="record_failure",
                from_state="executing",
                to_state=decision.next_state,
                metadata={
                    "reason": decision.reason,
                    "attempts": decision.attempts,
                    "failures": decision.failures,
                    "remainingAttempts": decision.remaining_attempts,
                    "remainingFailures": decision.remaining_failures,
                },
            )
            return decision
        if state.attempts == 0:
            state.attempts = 1
        state.failures += 1
        self._record_trace(
            run_id=item_id,
            event="retry_failure_recorded",
            step="record_failure",
            from_state="executing",
            to_state="executing",
            metadata={"attempts": state.attempts, "failures": state.failures},
        )

        attempts_exhausted = state.attempts >= self._policy.max_attempts
        failures_exhausted = state.failures >= self._policy.max_failures
        if attempts_exhausted or failures_exhausted:
            state.terminal = True
            reason = "attempt_budget_exhausted" if attempts_exhausted else "failure_budget_exhausted"
            decision = self._terminal_decision(state=state, reason=reason)
            self._record_trace(
                run_id=item_id,
                event="retry_terminal_decision",
                step="record_failure",
                from_state="executing",
                to_state=decision.next_state,
                metadata={
                    "reason": decision.reason,
                    "attempts": decision.attempts,
                    "failures": decision.failures,
                    "remainingAttempts": decision.remaining_attempts,
                    "remainingFailures": decision.remaining_failures,
                },
            )
            return decision

        retry_after_seconds = min(
            self._policy.base_backoff_seconds * (2 ** max(state.failures - 1, 0)),
            self._policy.max_backoff_seconds,
        )
        decision = RetryDecision(
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
        self._record_trace(
            run_id=item_id,
            event="retry_scheduled",
            step="record_failure",
            from_state="executing",
            to_state=decision.next_state,
            metadata={
                "reason": decision.reason,
                "retryAfterSeconds": retry_after_seconds,
                "attempts": decision.attempts,
                "failures": decision.failures,
                "remainingAttempts": decision.remaining_attempts,
                "remainingFailures": decision.remaining_failures,
            },
        )
        return decision

    def record_success(self, *, item_id: str) -> RetryRuntimeState:
        state = self._state_for(item_id)
        state.terminal = True
        self._record_trace(
            run_id=item_id,
            event="retry_success",
            step="record_success",
            from_state="executing",
            to_state="completed",
            metadata={
                "attempts": state.attempts,
                "failures": state.failures,
            },
        )
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

    def _record_trace(
        self,
        *,
        run_id: str,
        event: str,
        step: str,
        from_state: str | None,
        to_state: str | None,
        metadata: dict[str, object],
    ) -> None:
        if self._trace_service is None:
            return
        self._trace_service.record(
            run_id=run_id,
            event=event,
            step=step,
            from_state=from_state,
            to_state=to_state,
            identity=self._trace_identity,
            metadata=metadata,
        )


__all__ = [
    "OrchestratorRetryPolicyService",
    "RetryBudgetPolicy",
    "RetryDecision",
    "RetryRuntimeState",
]
