"""
LangGraph agent state definition.
"""

from operator import add
from typing import Annotated, Any, TypedDict

from app.models.query_analysis import QueryAnalysisResult


class AgentState(TypedDict):
    """
    State maintained throughout agent execution.

    LangGraph uses this TypedDict to track state across nodes.
    """

    # Input
    query: str
    session_id: str
    user_id: str | None
    province: str | None  # Canadian province context (MB, ON, SK, AB, BC)
    project_id: str | None  # Project UUID for project-based RAG (project docs + global KB)
    conversation_history: list[dict[str, Any]]  # Previous messages in this session
    user_settings: dict[str, Any] | None  # model_override, system_prompt_override (optional)

    # Query analysis
    query_analysis: QueryAnalysisResult | None

    # Tool invocation
    tool_results: Annotated[list[dict[str, Any]], add]
    tool_invocation_error: str | None

    # Retrieved context
    attachment_context: str  # Extracted text from chat file uploads (PDF, docx, etc.)
    context_documents: Annotated[list[dict[str, Any]], add]
    context_text: str

    # Agent reasoning
    confidence_score: float
    confidence_method: str | None  # "formula", "llm", or "hybrid"
    confidence_breakdown: dict[str, Any] | None  # Detailed confidence calculation data
    reasoning: str

    # Output
    response: str
    sources: list[dict[str, Any]]
    escalated: bool
    escalation_reason: str | None

    # Metadata
    tokens_used: int
    error: str | None

    # Prompt tracking (for analytics)
    prompt_versions_used: dict[str, str]  # {prompt_name: prompt_id}
