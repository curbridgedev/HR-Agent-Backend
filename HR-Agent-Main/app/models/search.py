"""
Search models for hybrid vector and keyword search with reranking.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """Filters for search queries."""

    source: str | None = Field(None, description="Filter by source (slack/whatsapp/telegram/admin)")
    author_id: str | None = Field(None, description="Filter by author ID")
    conversation_id: str | None = Field(None, description="Filter by conversation ID")
    start_date: datetime | None = Field(None, description="Filter messages after this date")
    end_date: datetime | None = Field(None, description="Filter messages before this date")


class SearchRequest(BaseModel):
    """Request for hybrid search."""

    query: str = Field(..., description="Search query text", min_length=1, max_length=500)
    match_count: int = Field(10, description="Maximum number of results", ge=1, le=50)
    match_threshold: float = Field(0.7, description="Minimum similarity score", ge=0.0, le=1.0)
    semantic_weight: float = Field(0.5, description="Weight for semantic search", ge=0.0, le=1.0)
    keyword_weight: float = Field(0.5, description="Weight for keyword search", ge=0.0, le=1.0)
    use_reranking: bool = Field(True, description="Whether to apply Cohere reranking")
    filters: SearchFilters | None = Field(None, description="Optional metadata filters")


class SearchResult(BaseModel):
    """Single search result."""

    id: UUID
    title: str
    content: str
    source: str
    author_name: str | None
    conversation_name: str | None
    timestamp: datetime | None
    semantic_score: float
    keyword_score: float
    combined_score: float
    rerank_score: float | None = Field(None, description="Cohere reranking score if applied")
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    """Response from hybrid search."""

    results: list[SearchResult]
    total_results: int
    query: str
    execution_time_ms: float
    reranking_applied: bool = Field(False, description="Whether Cohere reranking was applied")
