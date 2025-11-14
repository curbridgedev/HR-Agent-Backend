"""
Chat-related Pydantic models for request/response validation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import Field, field_validator
from app.models.base import BaseRequest, BaseResponse, TimestampMixin


class ChatMessage(BaseRequest):
    """Single chat message."""

    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate message role."""
        allowed_roles = ["user", "assistant", "system"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class ChatRequest(BaseRequest):
    """Chat request from user."""

    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: str = Field(..., description="Chat session ID for context tracking")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    context: Optional[List[ChatMessage]] = Field(
        None, description="Previous messages for context"
    )
    stream: bool = Field(False, description="Enable streaming response via SSE")
    province: Optional[str] = Field("MB", description="Canadian province context (MB, ON, SK, AB, BC)")


class SourceReference(BaseResponse):
    """Reference to a source document used in the response."""

    content: str = Field(..., description="Relevant content snippet")
    source: str = Field(..., description="Source identifier (Slack, WhatsApp, etc.)")
    timestamp: Optional[datetime] = Field(None, description="Source timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")


class ChatResponse(BaseResponse):
    """Chat response from agent."""

    message: str = Field(..., description="Agent response message")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Agent confidence score (0-1)"
    )
    sources: List[SourceReference] = Field(
        default_factory=list, description="Source documents used"
    )
    escalated: bool = Field(False, description="Whether query was escalated to human")
    escalation_reason: Optional[str] = Field(
        None, description="Reason for escalation if applicable"
    )
    session_id: str = Field(..., description="Chat session ID")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    tokens_used: Optional[int] = Field(None, description="Total tokens used")


class ChatStreamChunk(BaseResponse):
    """Single chunk of streamed chat response."""

    chunk: str = Field(..., description="Response chunk")
    is_final: bool = Field(False, description="Whether this is the final chunk")
    confidence: Optional[float] = Field(None, description="Confidence score (only in final chunk)")
    sources: Optional[List[SourceReference]] = Field(
        None, description="Sources (only in final chunk)"
    )


class ChatSession(BaseResponse, TimestampMixin):
    """Chat session metadata."""

    session_id: str = Field(..., description="Unique session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    messages: List[ChatMessage] = Field(default_factory=list, description="Session messages")
    active: bool = Field(True, description="Whether session is active")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Session metadata")


class SessionSummary(BaseResponse):
    """Summary of a chat session for the sessions list."""

    session_id: str = Field(..., description="UUID of the session")
    title: str = Field(..., description="First user message (truncated to 50 chars)")
    last_message: str = Field(..., description="Last message content (truncated to 100 chars)")
    message_count: int = Field(..., description="Total number of messages in session")
    province: Optional[str] = Field("MB", description="Province context for the session")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last message timestamp")


class SessionsListResponse(BaseResponse):
    """Paginated list of chat sessions."""

    sessions: List[SessionSummary] = Field(..., description="List of session summaries")
    total: int = Field(..., description="Total number of sessions")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of sessions per page")
    total_pages: int = Field(..., description="Total number of pages")
