"""
Normalized message schema for cross-platform data normalization.

This module defines the unified schema that all messages from different sources
(Slack, WhatsApp, Telegram, Admin Upload) are normalized into.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MessageSource(str, Enum):
    """Supported message sources."""

    SLACK = "slack"
    WHATSAPP = "whatsapp"
    WHATSAPP_EXPORT = "whatsapp_export"
    TELEGRAM = "telegram"
    ADMIN_UPLOAD = "admin_upload"


class MessageType(str, Enum):
    """Type of message content."""

    TEXT = "text"
    DOCUMENT = "document"
    MEDIA = "media"
    SYSTEM = "system"


class NormalizedAuthor(BaseModel):
    """Normalized author/sender information."""

    id: str = Field(..., description="Platform-specific user/sender ID")
    name: str | None = Field(None, description="Display name of the sender")
    platform_username: str | None = Field(None, description="Platform username (e.g., @username)")


class NormalizedConversation(BaseModel):
    """Normalized conversation/channel/chat information."""

    id: str = Field(..., description="Platform-specific conversation ID")
    name: str | None = Field(None, description="Conversation name")
    type: str | None = Field(None, description="Type: channel, group, private, etc.")


class NormalizedThread(BaseModel):
    """Normalized thread information for threaded messages."""

    parent_message_id: str | None = Field(None, description="ID of the parent message")
    is_thread_reply: bool = Field(False, description="Whether this is a reply in a thread")
    thread_timestamp: str | None = Field(None, description="Thread identifier (Slack thread_ts)")


class NormalizedMessage(BaseModel):
    """
    Unified message schema across all platforms.

    This is the normalized representation that all source-specific messages
    are converted into for consistent processing, deduplication, and storage.
    """

    # Core identifiers
    id: UUID = Field(..., description="Unique document ID in Supabase")
    source: MessageSource = Field(..., description="Platform source")
    source_message_id: str = Field(..., description="Platform-specific message ID")
    source_id: str = Field(..., description="Composite source identifier for deduplication")

    # Content
    content: str = Field(..., description="Message text content")
    content_hash: str | None = Field(None, description="SHA-256 hash for deduplication")
    message_type: MessageType = Field(default=MessageType.TEXT, description="Type of content")

    # Timestamps (normalized to UTC)
    timestamp: datetime = Field(..., description="Message creation timestamp (UTC)")
    ingested_at: datetime = Field(..., description="When message was ingested (UTC)")
    updated_at: datetime | None = Field(None, description="Last update timestamp for edits")

    # Author information
    author: NormalizedAuthor = Field(..., description="Normalized author/sender info")

    # Conversation context
    conversation: NormalizedConversation = Field(..., description="Normalized conversation info")

    # Thread information
    thread: NormalizedThread | None = Field(None, description="Thread context if applicable")

    # Platform-specific metadata (preserved for reference)
    platform_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Original platform-specific metadata"
    )

    # Processing metadata
    processing_status: str = Field(default="completed", description="Processing status")
    embedding_generated: bool = Field(False, description="Whether embedding was generated")

    # Edit tracking (for deduplication)
    is_edited: bool = Field(False, description="Whether message has been edited")
    previous_version_id: UUID | None = Field(None, description="ID of previous version if edited")
    version: int = Field(default=1, description="Version number (for tracking edits)")

    # Deduplication metadata
    duplicate_of: UUID | None = Field(
        None, description="ID of original if this is a duplicate across platforms"
    )
    is_duplicate: bool = Field(False, description="Whether this is marked as a duplicate")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
        use_enum_values = True


class SourceSpecificMetadata(BaseModel):
    """
    Container for source-specific metadata that doesn't fit the normalized schema.
    This preserves all original data for debugging and reference.
    """

    # Slack-specific
    slack_team_id: str | None = None
    slack_channel_id: str | None = None
    slack_message_ts: str | None = None

    # WhatsApp-specific
    whatsapp_phone_number_id: str | None = None
    whatsapp_wamid: str | None = None
    whatsapp_file_name: str | None = None

    # Telegram-specific
    telegram_chat_id: int | None = None
    telegram_message_id: int | None = None
    telegram_is_forwarded: bool | None = None

    # Admin upload-specific
    admin_upload_file_name: str | None = None
    admin_upload_chunk_index: int | None = None
    admin_upload_total_chunks: int | None = None


class DeduplicationResult(BaseModel):
    """Result of deduplication check."""

    is_duplicate: bool = Field(..., description="Whether message is a duplicate")
    duplicate_of_id: UUID | None = Field(None, description="ID of original message if duplicate")
    match_type: str | None = Field(
        None, description="Type of match: exact_content, cross_platform, edited_version"
    )
    confidence: float = Field(default=1.0, description="Confidence score of duplicate match")
    content_hash: str = Field(..., description="Hash used for comparison")


class NormalizationResult(BaseModel):
    """Result of message normalization."""

    success: bool = Field(..., description="Whether normalization succeeded")
    normalized_message: NormalizedMessage | None = Field(None, description="Normalized message")
    deduplication_result: DeduplicationResult | None = Field(
        None, description="Deduplication check result"
    )
    error: str | None = Field(None, description="Error message if normalization failed")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
