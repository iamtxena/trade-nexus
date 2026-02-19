"""Validation core package for portable module boundaries."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

_AGENT_EXPORTS: dict[str, str] = {
    "AgentReviewBudget": "AgentReviewBudget",
    "AgentReviewBudgetReport": "AgentReviewBudgetReport",
    "AgentReviewBudgetUsage": "AgentReviewBudgetUsage",
    "AgentReviewDecision": "ValidationDecision",
    "AgentReviewFinding": "AgentReviewFinding",
    "AgentReviewProfile": "ValidationProfile",
    "AgentReviewResult": "AgentReviewResult",
    "AgentReviewToolCall": "AgentReviewToolCall",
    "AgentReviewToolExecutor": "AgentReviewToolExecutor",
    "InMemoryAgentReviewToolExecutor": "InMemoryAgentReviewToolExecutor",
    "ValidationAgentReviewService": "ValidationAgentReviewService",
}

_DETERMINISTIC_EXPORTS: dict[str, str] = {
    "DeterministicValidationDecision": "ValidationDecision",
    "DeterministicValidationEngine": "DeterministicValidationEngine",
    "DeterministicValidationEvidence": "DeterministicValidationEvidence",
    "DeterministicValidationProfile": "ValidationProfile",
    "DeterministicValidationResult": "DeterministicValidationResult",
    "IndicatorFidelityCheckResult": "IndicatorFidelityCheckResult",
    "LineageCompletenessCheckResult": "LineageCompletenessCheckResult",
    "MetricConsistencyCheckResult": "MetricConsistencyCheckResult",
    "TradeCoherenceCheckResult": "TradeCoherenceCheckResult",
    "ValidationArtifactContext": "ValidationArtifactContext",
    "ValidationFinding": "ValidationFinding",
    "ValidationPolicyConfig": "ValidationPolicyConfig",
}

_PORTABLE_EXPORTS: dict[str, str] = {
    "PortableValidationDecision": "PortableValidationDecision",
    "PortableValidationModule": "PortableValidationModule",
    "PortableValidationResult": "PortableValidationResult",
}

__all__ = [
    "AgentReviewBudget",
    "AgentReviewBudgetReport",
    "AgentReviewBudgetUsage",
    "AgentReviewDecision",
    "AgentReviewFinding",
    "AgentReviewProfile",
    "AgentReviewResult",
    "AgentReviewToolCall",
    "AgentReviewToolExecutor",
    "DeterministicValidationDecision",
    "DeterministicValidationEngine",
    "DeterministicValidationEvidence",
    "DeterministicValidationProfile",
    "DeterministicValidationResult",
    "InMemoryAgentReviewToolExecutor",
    "IndicatorFidelityCheckResult",
    "LineageCompletenessCheckResult",
    "MetricConsistencyCheckResult",
    "PortableValidationDecision",
    "PortableValidationModule",
    "PortableValidationResult",
    "TradeCoherenceCheckResult",
    "ValidationAgentReviewService",
    "ValidationArtifactContext",
    "ValidationDecision",
    "ValidationFinding",
    "ValidationPolicyConfig",
    "ValidationProfile",
]

if TYPE_CHECKING:
    from src.platform_api.validation.core.agent_review import (
        AgentReviewBudget,
        AgentReviewBudgetReport,
        AgentReviewBudgetUsage,
        AgentReviewFinding,
        AgentReviewResult,
        AgentReviewToolCall,
        AgentReviewToolExecutor,
        InMemoryAgentReviewToolExecutor,
        ValidationAgentReviewService,
    )
    from src.platform_api.validation.core.agent_review import (
        ValidationDecision as AgentReviewDecision,
    )
    from src.platform_api.validation.core.agent_review import (
        ValidationProfile as AgentReviewProfile,
    )
    from src.platform_api.validation.core.deterministic import (
        DeterministicValidationEngine,
        DeterministicValidationEvidence,
        DeterministicValidationResult,
        IndicatorFidelityCheckResult,
        LineageCompletenessCheckResult,
        MetricConsistencyCheckResult,
        TradeCoherenceCheckResult,
        ValidationArtifactContext,
        ValidationFinding,
        ValidationPolicyConfig,
    )
    from src.platform_api.validation.core.deterministic import (
        ValidationDecision as DeterministicValidationDecision,
    )
    from src.platform_api.validation.core.deterministic import (
        ValidationProfile as DeterministicValidationProfile,
    )
    from src.platform_api.validation.core.portable import (
        PortableValidationDecision,
        PortableValidationModule,
        PortableValidationResult,
    )

    ValidationDecision = AgentReviewDecision
    ValidationProfile = DeterministicValidationProfile


def __getattr__(name: str) -> Any:
    if name in _AGENT_EXPORTS:
        module = import_module("src.platform_api.validation.core.agent_review")
        return getattr(module, _AGENT_EXPORTS[name])
    if name in _DETERMINISTIC_EXPORTS:
        module = import_module("src.platform_api.validation.core.deterministic")
        return getattr(module, _DETERMINISTIC_EXPORTS[name])
    if name in _PORTABLE_EXPORTS:
        module = import_module("src.platform_api.validation.core.portable")
        return getattr(module, _PORTABLE_EXPORTS[name])
    if name == "ValidationDecision":
        module = import_module("src.platform_api.validation.core.agent_review")
        return getattr(module, "ValidationDecision")
    if name == "ValidationProfile":
        module = import_module("src.platform_api.validation.core.deterministic")
        return getattr(module, "ValidationProfile")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
