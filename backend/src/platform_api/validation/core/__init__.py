"""Validation core package for portable module boundaries."""

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

# Backward-compatible aliases at the package level.
ValidationDecision = AgentReviewDecision
ValidationProfile = DeterministicValidationProfile

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
