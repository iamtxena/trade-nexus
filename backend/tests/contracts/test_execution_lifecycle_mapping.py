"""Tests for canonical execution lifecycle transition mapping."""

from src.platform_api.services.execution_lifecycle_mapping import (
    apply_deployment_transition,
    map_provider_deployment_status,
)


def test_provider_status_map_handles_known_and_unknown_values() -> None:
    assert map_provider_deployment_status("active") == "running"
    assert map_provider_deployment_status("halting") == "stopping"
    assert map_provider_deployment_status("unexpected") == "failed"


def test_transition_rules_prevent_invalid_regressions() -> None:
    assert apply_deployment_transition("queued", "running") == "running"
    assert apply_deployment_transition("running", "stopping") == "stopping"
    assert apply_deployment_transition("stopped", "running") == "stopped"
    assert apply_deployment_transition("failed", "running") == "failed"
