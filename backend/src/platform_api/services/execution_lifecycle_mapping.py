"""Canonical execution lifecycle transition mapping."""

from __future__ import annotations

DeploymentState = str

VALID_DEPLOYMENT_STATES: set[DeploymentState] = {
    "queued",
    "running",
    "paused",
    "stopping",
    "stopped",
    "failed",
}

ALLOWED_DEPLOYMENT_TRANSITIONS: dict[DeploymentState, set[DeploymentState]] = {
    "queued": {"queued", "running", "failed", "stopping", "stopped"},
    "running": {"running", "paused", "stopping", "stopped", "failed"},
    "paused": {"paused", "running", "stopping", "stopped", "failed"},
    "stopping": {"stopping", "stopped", "failed"},
    "stopped": {"stopped"},
    "failed": {"failed"},
}

PROVIDER_STATUS_MAP: dict[str, DeploymentState] = {
    "queued": "queued",
    "pending": "queued",
    "starting": "queued",
    "running": "running",
    "active": "running",
    "paused": "paused",
    "halting": "stopping",
    "stopping": "stopping",
    "stopped": "stopped",
    "terminated": "stopped",
    "failed": "failed",
    "error": "failed",
}


def map_provider_deployment_status(raw_status: str | None) -> DeploymentState:
    if not raw_status:
        return "failed"
    return PROVIDER_STATUS_MAP.get(raw_status.lower(), "failed")


def is_valid_transition(current: DeploymentState, target: DeploymentState) -> bool:
    if current not in VALID_DEPLOYMENT_STATES or target not in VALID_DEPLOYMENT_STATES:
        return False
    return target in ALLOWED_DEPLOYMENT_TRANSITIONS[current]


def apply_deployment_transition(current: DeploymentState, provider_status: str | None) -> DeploymentState:
    target = map_provider_deployment_status(provider_status)
    if current not in VALID_DEPLOYMENT_STATES:
        return target
    if is_valid_transition(current, target):
        return target
    if current in {"stopped", "failed"}:
        return current
    if target == "failed":
        return "failed"
    return current
