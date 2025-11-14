"""
Agent configuration models.

Pydantic models for agent configuration management with versioning.
"""

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.models.base import BaseRequest, BaseResponse

# Configuration sub-models for type safety

class ConfidenceThresholds(BaseRequest):
    """Confidence threshold settings."""

    escalation: float = Field(0.95, ge=0.0, le=1.0, description="Threshold for escalation")
    high: float = Field(0.85, ge=0.0, le=1.0, description="High confidence threshold")
    medium: float = Field(0.70, ge=0.0, le=1.0, description="Medium confidence threshold")
    low: float = Field(0.50, ge=0.0, le=1.0, description="Low confidence threshold")


class ModelSettings(BaseRequest):
    """LLM model configuration with multi-provider support."""

    provider: str = Field("openai", description="LLM provider (openai, anthropic, google)")
    model: str = Field("gpt-4", description="Model name")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(1000, ge=1, le=4096, description="Maximum tokens")
    top_p: float = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling")
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider is supported."""
        allowed = ["openai", "anthropic", "google"]
        if v not in allowed:
            raise ValueError(f"Provider must be one of: {', '.join(allowed)}")
        return v


class SearchSettings(BaseRequest):
    """Vector search configuration."""

    similarity_threshold: float = Field(
        0.7, ge=0.0, le=1.0, description="Similarity threshold"
    )
    max_results: int = Field(5, ge=1, le=50, description="Maximum search results")
    use_hybrid_search: bool = Field(True, description="Enable hybrid search")


class ToolConfig(BaseRequest):
    """Individual tool configuration."""

    timeout_ms: int = Field(5000, ge=100, description="Timeout in milliseconds")
    max_results: int | None = Field(None, ge=1, description="Max results for tool")


class ToolRegistry(BaseRequest):
    """Tool registry configuration."""

    enabled_tools: list[str] = Field(
        default_factory=list, description="List of enabled tool names"
    )
    tool_configs: dict[str, ToolConfig] = Field(
        default_factory=dict, description="Tool-specific configurations"
    )


class FeatureFlags(BaseRequest):
    """Feature flag settings."""

    enable_pii_anonymization: bool = Field(True, description="Enable PII anonymization")
    enable_semantic_cache: bool = Field(False, description="Enable semantic caching")
    enable_query_rewriting: bool = Field(False, description="Enable query rewriting")
    enable_confidence_calibration: bool = Field(
        True, description="Enable confidence calibration"
    )
    enable_debug_logging: bool = Field(False, description="Enable debug logging")


class RateLimits(BaseRequest):
    """Rate limiting configuration."""

    max_requests_per_minute: int = Field(
        60, ge=1, description="Max requests per minute"
    )
    max_tokens_per_minute: int = Field(
        90000, ge=1000, description="Max tokens per minute"
    )


# Confidence Calculation Configuration Models

class FormulaWeights(BaseRequest):
    """Weights for formula-based confidence calculation."""

    similarity: float = Field(
        0.80, ge=0.0, le=1.0, description="Weight for similarity score"
    )
    source_quality: float = Field(
        0.10, ge=0.0, le=1.0, description="Weight for high-quality source count"
    )
    response_length: float = Field(
        0.10, ge=0.0, le=1.0, description="Weight for response completeness"
    )

    @field_validator("response_length")
    @classmethod
    def validate_weights_sum(cls, v: float, info) -> float:
        """Validate that all weights sum to 1.0."""
        similarity = info.data.get("similarity", 0.80)
        source_quality = info.data.get("source_quality", 0.10)
        total = similarity + source_quality + v

        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Formula weights must sum to 1.0 (got {total:.2f}). "
                f"similarity={similarity}, source_quality={source_quality}, "
                f"response_length={v}"
            )
        return v


class HybridConfidenceSettings(BaseRequest):
    """Settings for hybrid confidence calculation (formula + LLM)."""

    formula_weight: float = Field(
        0.60, ge=0.0, le=1.0, description="Weight for formula score"
    )
    llm_weight: float = Field(
        0.40, ge=0.0, le=1.0, description="Weight for LLM score"
    )

    @field_validator("llm_weight")
    @classmethod
    def validate_weights_sum(cls, v: float, info) -> float:
        """Validate that formula_weight + llm_weight = 1.0."""
        formula_weight = info.data.get("formula_weight", 0.60)
        total = formula_weight + v

        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Hybrid weights must sum to 1.0 (got {total:.2f}). "
                f"formula_weight={formula_weight}, llm_weight={v}"
            )
        return v


class LLMConfidenceSettings(BaseRequest):
    """Settings for LLM-based confidence evaluation."""

    provider: str = Field(
        "openai",
        description="LLM provider (only OpenAI is supported)",
    )
    model: str = Field(
        "gpt-4o-mini", description="Model name for confidence evaluation"
    )
    temperature: float = Field(
        0.1, ge=0.0, le=2.0, description="LLM temperature (lower = more deterministic)"
    )
    max_tokens: int = Field(
        100, ge=10, le=500, description="Maximum tokens for confidence response"
    )
    timeout_ms: int = Field(
        2000, ge=100, le=10000, description="Timeout in milliseconds (fallback to formula on timeout)"
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider is supported."""
        if v != "openai":
            raise ValueError("Provider must be 'openai' (only provider with configured API key)")
        return v


class ConfidenceCalculationConfig(BaseRequest):
    """
    Configuration for confidence calculation method.

    Supports three methods:
    - formula: Fast, algorithmic calculation based on retrieval metrics (free)
    - llm: Semantic evaluation using LLM (accurate, LLM cost per query)
    - hybrid: Combination of both (always calculates both and combines with weights)
    """

    method: str = Field(
        "formula",
        description="Calculation method: formula, llm, or hybrid",
    )
    hybrid_settings: HybridConfidenceSettings = Field(
        default_factory=HybridConfidenceSettings,
        description="Weights for hybrid mode",
    )
    llm_settings: LLMConfidenceSettings = Field(
        default_factory=LLMConfidenceSettings,
        description="LLM configuration for llm and hybrid modes",
    )
    formula_weights: FormulaWeights = Field(
        default_factory=FormulaWeights,
        description="Weights for formula calculation",
    )

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate method is one of allowed values."""
        allowed = ["formula", "llm", "hybrid"]
        if v not in allowed:
            raise ValueError(f"Method must be one of: {', '.join(allowed)}")
        return v


class AgentConfigData(BaseRequest):
    """
    Complete agent configuration data structure.

    This matches the JSONB 'config' column in the database.
    """

    confidence_thresholds: ConfidenceThresholds = Field(
        default_factory=ConfidenceThresholds
    )
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    search_settings: SearchSettings = Field(default_factory=SearchSettings)
    tool_registry: ToolRegistry = Field(default_factory=ToolRegistry)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)
    rate_limits: RateLimits = Field(default_factory=RateLimits)
    confidence_calculation: ConfidenceCalculationConfig = Field(
        default_factory=ConfidenceCalculationConfig,
        description="Confidence calculation configuration",
    )


# API models

class AgentConfigBase(BaseRequest):
    """Base agent config model."""

    name: str = Field(..., description="Configuration name")
    environment: str = Field(
        "all",
        description="Target environment: development, uat, production, or all",
    )
    config: AgentConfigData = Field(..., description="Configuration data")
    description: str | None = Field(None, description="Configuration description")
    tags: list[str] = Field(default_factory=list, description="Tags")
    notes: str | None = Field(None, description="Version notes")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of allowed values."""
        allowed = ["development", "uat", "production", "all"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {', '.join(allowed)}")
        return v


class AgentConfigCreate(AgentConfigBase):
    """Model for creating a new config version."""

    created_by: str | None = Field(None, description="Creator username")
    activate_immediately: bool = Field(
        False, description="Activate this version immediately"
    )


class AgentConfigUpdate(BaseRequest):
    """Model for updating a config."""

    config: AgentConfigData | None = Field(None, description="Updated configuration")
    description: str | None = Field(None, description="Updated description")
    tags: list[str] | None = Field(None, description="Updated tags")
    notes: str | None = Field(None, description="Update notes")


class AgentConfigResponse(BaseResponse):
    """Model for agent config response."""

    id: UUID = Field(..., description="Config UUID")
    name: str = Field(..., description="Config name")
    version: int = Field(..., description="Version number")
    environment: str = Field(..., description="Target environment")
    config: AgentConfigData = Field(..., description="Configuration data")
    active: bool = Field(..., description="Whether this version is active")
    description: str | None = Field(None, description="Description")
    tags: list[str] = Field(default_factory=list, description="Tags")

    # Performance tracking
    usage_count: int = Field(0, description="Usage count")
    avg_response_time_ms: float | None = Field(
        None, description="Average response time"
    )
    avg_confidence: float | None = Field(None, description="Average confidence")
    escalation_rate: float | None = Field(None, description="Escalation rate")
    success_rate: float | None = Field(None, description="Success rate")

    # Audit
    created_by: str | None = Field(None, description="Creator")
    notes: str | None = Field(None, description="Version notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class AgentConfigListResponse(BaseResponse):
    """Model for listing agent configs."""

    configs: list[AgentConfigResponse] = Field(..., description="List of configs")
    total: int = Field(..., description="Total count")
    page: int = Field(1, description="Current page")
    page_size: int = Field(50, description="Page size")


class AgentConfigActivateRequest(BaseRequest):
    """Model for activating a config version."""

    config_id: UUID = Field(..., description="ID of config version to activate")


class AgentConfigVersionCreateResponse(BaseResponse):
    """Model for config version creation response."""

    config_id: UUID = Field(..., description="ID of newly created config version")
    version: int = Field(..., description="Version number")
    active: bool = Field(..., description="Whether version was activated")
