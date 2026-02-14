"""Tests for canonical execution lifecycle transition mapping."""

from src.platform_api.services.execution_lifecycle_mapping import (
    apply_deployment_transition,
    apply_order_transition,
    map_provider_deployment_status,
    map_provider_order_status,
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


def test_order_status_map_handles_known_and_unknown_values() -> None:
    assert map_provider_order_status("open") == "pending"
    assert map_provider_order_status("executed") == "filled"
    assert map_provider_order_status("canceled") == "cancelled"
    assert map_provider_order_status("unexpected") == "failed"


def test_order_transition_rules_keep_terminal_states() -> None:
    assert apply_order_transition("pending", "filled") == "filled"
    assert apply_order_transition("pending", "cancelled") == "cancelled"
    assert apply_order_transition("pending", "processing") == "failed"
    assert apply_order_transition("filled", "cancelled") == "filled"
    assert apply_order_transition("cancelled", "filled") == "cancelled"
    assert apply_order_transition("failed", "pending") == "failed"
