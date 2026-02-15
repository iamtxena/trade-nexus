"""Contract tests for AG-ORCH-03 retry/failure budget policy."""

from __future__ import annotations

import pytest

from src.platform_api.services.orchestrator_retry_policy import (
    OrchestratorRetryPolicyService,
    RetryBudgetPolicy,
)


def test_retry_policy_is_deterministic_and_bounded() -> None:
    service = OrchestratorRetryPolicyService(
        policy=RetryBudgetPolicy(
            max_attempts=3,
            max_failures=3,
            base_backoff_seconds=2,
            max_backoff_seconds=30,
        )
    )

    service.begin_attempt(item_id="orch-001")
    first = service.record_failure(item_id="orch-001")
    assert first.retry_allowed is True
    assert first.next_state == "awaiting_tool"
    assert first.retry_after_seconds == 2

    service.begin_attempt(item_id="orch-001")
    second = service.record_failure(item_id="orch-001")
    assert second.retry_allowed is True
    assert second.next_state == "awaiting_tool"
    assert second.retry_after_seconds == 4

    service.begin_attempt(item_id="orch-001")
    third = service.record_failure(item_id="orch-001")
    assert third.retry_allowed is False
    assert third.terminal is True
    assert third.next_state == "failed"
    assert third.reason == "attempt_budget_exhausted"


def test_failure_budget_exhaustion_precedes_attempt_budget() -> None:
    service = OrchestratorRetryPolicyService(
        policy=RetryBudgetPolicy(
            max_attempts=5,
            max_failures=2,
            base_backoff_seconds=1,
            max_backoff_seconds=30,
        )
    )

    service.begin_attempt(item_id="orch-002")
    first = service.record_failure(item_id="orch-002")
    assert first.retry_allowed is True

    service.begin_attempt(item_id="orch-002")
    second = service.record_failure(item_id="orch-002")
    assert second.retry_allowed is False
    assert second.terminal is True
    assert second.reason == "failure_budget_exhausted"


def test_begin_attempt_fails_after_terminal_state() -> None:
    service = OrchestratorRetryPolicyService(
        policy=RetryBudgetPolicy(
            max_attempts=1,
            max_failures=1,
        )
    )

    service.begin_attempt(item_id="orch-003")
    decision = service.record_failure(item_id="orch-003")
    assert decision.terminal is True

    with pytest.raises(ValueError):
        service.begin_attempt(item_id="orch-003")


def test_success_marks_retry_state_terminal() -> None:
    service = OrchestratorRetryPolicyService()
    service.begin_attempt(item_id="orch-004")
    state = service.record_success(item_id="orch-004")
    assert state.terminal is True

    snapshot = service.snapshot(item_id="orch-004")
    assert snapshot.attempts == 1
    assert snapshot.failures == 0
    assert snapshot.terminal is True
