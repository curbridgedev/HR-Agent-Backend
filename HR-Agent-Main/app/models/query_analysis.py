"""
Query analysis models for intent classification and entity extraction.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import Field
from app.models.base import BaseRequest, BaseResponse


class QueryIntent(str, Enum):
    """
    Intent classification for user queries.

    Determines what the user is trying to accomplish.
    """

    FACTUAL = "factual"  # Simple fact retrieval
    INFORMATIONAL = "informational"  # General information requests
    PROCEDURAL = "procedural"  # How-to, step-by-step instructions
    TROUBLESHOOTING = "troubleshooting"  # Problem-solving, debugging
    COMPARISON = "comparison"  # Comparing options or features
    DEFINITION = "definition"  # Defining terms or concepts
    CONCEPTUAL = "conceptual"  # Explaining abstract concepts
    NAVIGATIONAL = "navigational"  # Finding specific resources
    TRANSACTIONAL = "transactional"  # Action-oriented requests
    UNKNOWN = "unknown"  # Unable to classify


class QueryComplexity(str, Enum):
    """
    Query complexity assessment.

    Determines computational and reasoning requirements.
    """

    SIMPLE = "simple"  # Single fact, direct answer
    MODERATE = "moderate"  # Synthesis of 2-5 facts
    COMPLEX = "complex"  # Multi-step reasoning, 5+ facts
    VERY_COMPLEX = "very_complex"  # Deep analysis, extensive reasoning


class EntityType(str, Enum):
    """
    Types of entities that can be extracted from queries.
    """

    PRODUCT = "product"  # Compaytence features/products
    PAYMENT_METHOD = "payment_method"  # Payment types
    TECHNOLOGY = "technology"  # Technical terms (API, SDK)
    CONCEPT = "concept"  # Abstract concepts (compliance, security)
    COMPANY = "company"  # Organization names
    AMOUNT = "amount"  # Monetary amounts
    DATE = "date"  # Time references
    CURRENCY = "currency"  # Currency types
    COUNTRY = "country"  # Geographic references
    FEATURE = "feature"  # Specific features or capabilities


class ExtractedEntity(BaseRequest):
    """
    Entity extracted from query text.
    """

    text: str = Field(..., description="The entity text as it appears in query")
    type: EntityType = Field(..., description="Type of entity")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RoutingDecision(str, Enum):
    """
    Routing decision based on query analysis.
    """

    STANDARD_RAG = "standard_rag"  # Normal retrieval + generation
    TOOL_INVOCATION = "tool_invocation"  # Requires external tools
    MULTI_STEP_REASONING = "multi_step_reasoning"  # Complex reasoning chain
    DIRECT_ESCALATION = "direct_escalation"  # Out of scope, escalate immediately
    CACHED_RESPONSE = "cached_response"  # Check semantic cache first


class QueryAnalysisResult(BaseResponse):
    """
    Comprehensive query analysis result.

    Contains all information extracted from query analysis.
    """

    # Original query
    original_query: str = Field(..., description="Original user query")

    # Intent classification
    intent: QueryIntent = Field(..., description="Detected intent")
    intent_confidence: float = Field(..., ge=0.0, le=1.0, description="Intent classification confidence")

    # Complexity assessment
    complexity: QueryComplexity = Field(..., description="Query complexity level")
    complexity_score: float = Field(..., ge=0.0, le=1.0, description="Complexity score")

    # Entity extraction
    entities: List[ExtractedEntity] = Field(default_factory=list, description="Extracted entities")

    # Routing decision
    routing: RoutingDecision = Field(..., description="Recommended routing strategy")
    routing_confidence: float = Field(..., ge=0.0, le=1.0, description="Routing decision confidence")

    # Context requirements
    requires_recent_context: bool = Field(False, description="Needs recent/updated information")
    requires_multiple_sources: bool = Field(False, description="Needs multiple document sources")
    suggested_doc_count: int = Field(5, ge=1, le=20, description="Suggested number of docs to retrieve")
    suggested_similarity_threshold: float = Field(0.45, ge=0.0, le=1.0, description="Suggested similarity threshold (lowered for better recall)")

    # Tool requirements
    requires_tools: bool = Field(False, description="Requires external tool invocation")
    suggested_tools: List[str] = Field(default_factory=list, description="Suggested tools to use")

    # Query understanding
    key_concepts: List[str] = Field(default_factory=list, description="Key concepts in query")
    query_topics: List[str] = Field(default_factory=list, description="Main topics")

    # Metadata
    analysis_reasoning: str = Field("", description="Explanation of analysis decisions")
    analysis_time_ms: Optional[float] = Field(None, description="Time taken for analysis")


class QueryRewriteSuggestion(BaseResponse):
    """
    Suggestion for query rewriting/clarification.
    """

    original_query: str = Field(..., description="Original query")
    rewritten_query: str = Field(..., description="Improved/clarified query")
    rewrite_reason: str = Field(..., description="Why rewriting was suggested")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Rewrite quality confidence")


# Predefined domain knowledge for Compaytence
COMPAYTENCE_PRODUCTS = [
    "compaytence",
    "payment api",
    "payment sdk",
    "payment gateway",
    "payment processing",
    "payment platform",
]

PAYMENT_METHODS = [
    "credit card",
    "debit card",
    "ach",
    "wire transfer",
    "bank transfer",
    "digital wallet",
    "apple pay",
    "google pay",
    "paypal",
    "venmo",
    "cryptocurrency",
    "bitcoin",
]

PAYMENT_CONCEPTS = [
    "compliance",
    "pci dss",
    "security",
    "encryption",
    "tokenization",
    "fraud detection",
    "chargeback",
    "refund",
    "settlement",
    "reconciliation",
    "3d secure",
    "two-factor authentication",
]

TECHNICAL_TERMS = [
    "api",
    "sdk",
    "webhook",
    "rest",
    "graphql",
    "json",
    "xml",
    "authentication",
    "authorization",
    "oauth",
    "jwt",
    "token",
    "endpoint",
    "integration",
]
