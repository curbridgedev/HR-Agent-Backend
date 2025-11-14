"""
Source configuration models for chat platform integrations.
"""

from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import Field, field_validator
from app.models.base import BaseRequest, BaseResponse, TimestampMixin


SourceType = Literal["slack", "whatsapp", "telegram"]


class SourceConfigRequest(BaseRequest):
    """Request to configure a new data source."""

    source_type: SourceType = Field(..., description="Type of source to connect")
    credentials: Dict[str, str] = Field(..., description="Source-specific credentials")
    enabled: bool = Field(True, description="Whether source is enabled")
    ingest_historical: bool = Field(
        False, description="Whether to ingest historical messages"
    )
    historical_days: Optional[int] = Field(
        30, ge=1, le=365, description="Days of history to ingest"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator("credentials")
    @classmethod
    def validate_credentials(cls, v: Dict[str, str], info) -> Dict[str, str]:
        """Validate credentials based on source type."""
        source_type = info.data.get("source_type")

        required_keys = {
            "slack": ["bot_token", "signing_secret"],
            "whatsapp": ["access_token", "phone_number_id"],
            "telegram": ["bot_token"],
        }

        if source_type in required_keys:
            missing = set(required_keys[source_type]) - set(v.keys())
            if missing:
                raise ValueError(
                    f"Missing required credentials for {source_type}: {', '.join(missing)}"
                )

        return v


class SourceConfigResponse(BaseResponse):
    """Response after configuring a source."""

    source_id: str = Field(..., description="Unique source identifier")
    source_type: SourceType = Field(..., description="Type of source")
    status: str = Field(
        ..., description="Configuration status: pending, connected, failed"
    )
    message: str = Field(..., description="Status message")
    webhook_url: Optional[str] = Field(
        None, description="Webhook URL for real-time ingestion"
    )
    job_id: Optional[str] = Field(
        None, description="Background job ID for historical ingestion"
    )


class Source(BaseResponse, TimestampMixin):
    """Complete source configuration."""

    source_id: str = Field(..., description="Unique source identifier")
    source_type: SourceType = Field(..., description="Type of source")
    enabled: bool = Field(True, description="Whether source is enabled")
    status: str = Field(..., description="Connection status")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    last_sync_at: Optional[datetime] = Field(None, description="Last successful sync")
    message_count: int = Field(0, description="Total messages ingested")
    error_count: int = Field(0, description="Number of ingestion errors")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Source metadata")


class SourceListResponse(BaseResponse):
    """Response listing all configured sources."""

    sources: list[Source] = Field(default_factory=list, description="List of sources")
    total_count: int = Field(..., description="Total number of sources")


class SourceTestRequest(BaseRequest):
    """Request to test source connection."""

    source_type: SourceType = Field(..., description="Type of source to test")
    credentials: Dict[str, str] = Field(..., description="Source credentials to test")


class SourceTestResponse(BaseResponse):
    """Response from source connection test."""

    success: bool = Field(..., description="Whether connection test succeeded")
    message: str = Field(..., description="Test result message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional test details")


class WebhookEvent(BaseRequest):
    """Incoming webhook event from chat platform."""

    source_type: SourceType = Field(..., description="Source platform")
    event_type: str = Field(..., description="Type of event (message, etc.)")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
