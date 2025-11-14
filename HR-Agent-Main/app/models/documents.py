"""
Document-related Pydantic models for uploads and ingestion.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import Field, field_validator
from app.models.base import BaseRequest, BaseResponse, TimestampMixin


class DocumentUploadRequest(BaseRequest):
    """Request for document upload."""

    file_name: str = Field(..., description="Original file name")
    file_type: str = Field(..., description="MIME type of file")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    source: str = Field("admin_upload", description="Upload source")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        """Validate file size against maximum."""
        max_size_mb = 50  # From config
        max_size_bytes = max_size_mb * 1024 * 1024
        if v > max_size_bytes:
            raise ValueError(f"File size exceeds maximum of {max_size_mb}MB")
        return v


class DocumentUploadResponse(BaseResponse):
    """Response after document upload."""

    document_id: str = Field(..., description="Unique document identifier")
    status: str = Field(..., description="Upload status: pending, processing, completed, failed")
    message: str = Field(..., description="Status message")
    job_id: Optional[str] = Field(None, description="Background job ID for processing")


class DocumentChunk(BaseResponse):
    """A chunk of a processed document."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Chunk content")
    chunk_index: int = Field(..., ge=0, description="Chunk index in document")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class Document(BaseResponse, TimestampMixin):
    """Complete document record."""

    document_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Full document content")
    source: str = Field(..., description="Document source (Slack, WhatsApp, etc.)")
    source_id: Optional[str] = Field(None, description="Original source message/file ID")
    file_type: Optional[str] = Field(None, description="File type if applicable")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="Document chunks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    processing_status: str = Field(
        "pending",
        description="Processing status: pending, processing, completed, failed",
    )
    error_message: Optional[str] = Field(None, description="Error message if processing failed")


class DocumentSearchRequest(BaseRequest):
    """Request for document search."""

    query: str = Field(..., min_length=1, description="Search query")
    source_filter: Optional[List[str]] = Field(
        None, description="Filter by sources (e.g., ['slack', 'telegram'])"
    )
    date_from: Optional[datetime] = Field(None, description="Filter by start date")
    date_to: Optional[datetime] = Field(None, description="Filter by end date")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")


class DocumentSearchResult(BaseResponse):
    """Single document search result."""

    document_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    content_snippet: str = Field(..., description="Relevant content snippet")
    source: str = Field(..., description="Document source")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    timestamp: datetime = Field(..., description="Document timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentSearchResponse(BaseResponse):
    """Response for document search."""

    results: List[DocumentSearchResult] = Field(
        default_factory=list, description="Search results"
    )
    total_count: int = Field(..., description="Total matching documents")
    query_time_ms: int = Field(..., description="Query execution time in milliseconds")


class DocumentListItem(BaseResponse):
    """Document list item for browsing."""

    id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title")
    source: str = Field(..., description="Document source")
    processing_status: str = Field(..., description="Current processing status")
    created_at: datetime = Field(..., description="Upload timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentListResponse(BaseResponse):
    """Paginated list of documents."""

    documents: List[DocumentListItem] = Field(default_factory=list, description="List of documents")
    total: int = Field(..., description="Total number of documents")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class DocumentDetail(BaseResponse):
    """Detailed document information."""

    id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Full document content")
    source: str = Field(..., description="Document source")
    source_id: Optional[str] = Field(None, description="Original source ID")
    source_metadata: Dict[str, Any] = Field(default_factory=dict, description="Source-specific metadata")
    processing_status: str = Field(..., description="Processing status")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class DocumentDeleteResponse(BaseResponse):
    """Response after document deletion."""

    document_id: str = Field(..., description="Deleted document ID")
    message: str = Field("Document deleted successfully", description="Deletion confirmation")
