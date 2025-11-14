"""
Slack webhook event models and validation schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import Field, field_validator
from app.models.base import BaseRequest, BaseResponse


class SlackEvent(BaseRequest):
    """Base Slack event structure."""

    type: str = Field(..., description="Event type (e.g., 'message', 'app_mention')")
    user: Optional[str] = Field(None, description="User ID who triggered the event")
    text: Optional[str] = Field(None, description="Message text")
    channel: str = Field(..., description="Channel ID")
    ts: str = Field(..., description="Timestamp of the event")
    channel_type: Optional[str] = Field(None, description="Channel type (e.g., 'channel', 'im')")
    thread_ts: Optional[str] = Field(None, description="Thread timestamp if in thread")
    files: Optional[List[Dict[str, Any]]] = Field(None, description="Attached files")


class SlackChallenge(BaseRequest):
    """Slack URL verification challenge."""

    token: str = Field(..., description="Verification token")
    challenge: str = Field(..., description="Challenge string to echo back")
    type: str = Field(..., description="Should be 'url_verification'")


class SlackEventWrapper(BaseRequest):
    """Wrapper for Slack event callbacks."""

    token: str = Field(..., description="Verification token")
    team_id: str = Field(..., description="Workspace/team ID")
    api_app_id: str = Field(..., description="App ID")
    event: SlackEvent = Field(..., description="The actual event")
    type: str = Field(..., description="Should be 'event_callback'")
    event_id: str = Field(..., description="Unique event ID")
    event_time: int = Field(..., description="Unix timestamp")
    authorizations: Optional[List[Dict[str, Any]]] = Field(None, description="Authorization info")


class SlackFileInfo(BaseRequest):
    """Slack file attachment information."""

    id: str = Field(..., description="File ID")
    name: str = Field(..., description="File name")
    title: Optional[str] = Field(None, description="File title")
    mimetype: str = Field(..., description="MIME type")
    filetype: str = Field(..., description="File type")
    size: int = Field(..., description="File size in bytes")
    url_private: str = Field(..., description="Private download URL")
    url_private_download: str = Field(..., description="Private download URL (direct)")


class SlackMessageResponse(BaseResponse):
    """Response for posting messages to Slack."""

    channel: str = Field(..., description="Channel ID where message was posted")
    ts: str = Field(..., description="Timestamp of posted message")
    message_ts: Optional[str] = Field(None, description="Thread timestamp if reply")


class SlackWebhookResponse(BaseResponse):
    """Response from Slack webhook processing."""

    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    event_id: Optional[str] = Field(None, description="Slack event ID")
    response_sent: bool = Field(False, description="Whether response was sent to Slack")
