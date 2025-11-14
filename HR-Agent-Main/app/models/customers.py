"""
Customer, API Key, and Widget Configuration API models.

Pydantic models for customer management, API key generation,
and widget configuration endpoints.
"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import Field, EmailStr, field_validator, ConfigDict
from app.models.base import BaseRequest, BaseResponse


# ============================================================================
# Customer Models
# ============================================================================

class CustomerBase(BaseResponse):
    """Base customer fields shared across responses."""

    name: str = Field(..., description="Customer name")
    email: Optional[EmailStr] = Field(None, description="Customer email (unique)")
    company: Optional[str] = Field(None, description="Company name")
    enabled: bool = Field(True, description="Whether customer is active")
    metadata: dict = Field(default_factory=dict, description="Additional metadata (JSONB)")


class CustomerCreateRequest(BaseRequest):
    """Request model for creating new customer."""

    name: str = Field(..., min_length=1, max_length=255, description="Customer name")
    email: Optional[EmailStr] = Field(None, description="Customer email (must be unique)")
    company: Optional[str] = Field(None, max_length=255, description="Company name")
    enabled: bool = Field(True, description="Whether customer starts enabled")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class CustomerUpdateRequest(BaseRequest):
    """Request model for updating customer (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = Field(None)
    company: Optional[str] = Field(None, max_length=255)
    enabled: Optional[bool] = Field(None)
    metadata: Optional[dict] = Field(None)


class CustomerListItem(CustomerBase):
    """Customer list item (without related data)."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseResponse):
    """Response model for paginated customer list."""

    customers: List[CustomerListItem] = Field(..., description="List of customers")
    total_count: int = Field(..., description="Total number of customers")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# API Key Models
# ============================================================================

class APIKeyBase(BaseResponse):
    """Base API key fields (never includes full key hash)."""

    id: UUID
    key_prefix: str = Field(..., description="First 16 chars (e.g., 'cp_live_abc12345')")
    name: Optional[str] = Field(None, description="Optional key description")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    created_at: datetime
    expires_at: Optional[datetime] = Field(None, description="Expiry timestamp")
    enabled: bool = Field(..., description="Whether key is active")
    rate_limit_per_minute: int = Field(60, description="Requests per minute limit")
    rate_limit_per_day: int = Field(10000, description="Requests per day limit")


class APIKeyCreateRequest(BaseRequest):
    """Request model for generating new API key."""

    name: Optional[str] = Field(None, max_length=255, description="Optional key description")
    expires_at: Optional[datetime] = Field(None, description="Optional expiry (ISO 8601)")
    rate_limit_per_minute: int = Field(60, ge=1, le=1000, description="Requests per minute")
    rate_limit_per_day: int = Field(10000, ge=1, le=1000000, description="Requests per day")


class APIKeyCreateResponse(APIKeyBase):
    """
    Response for newly created API key.

    ⚠️ CRITICAL: Full API key is ONLY shown in this response, never again!
    """

    api_key: str = Field(
        ...,
        description="⚠️ FULL API KEY - ONLY SHOWN ONCE! Format: cp_live_<32_hex_chars>"
    )


class APIKeyListResponse(BaseResponse):
    """Response model for listing customer API keys."""

    api_keys: List[APIKeyBase] = Field(..., description="List of API keys (no full keys)")
    total_count: int = Field(..., description="Total number of keys")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Widget Configuration Models
# ============================================================================

class WidgetPosition(str):
    """Allowed widget positions."""
    BOTTOM_RIGHT = "bottom-right"
    BOTTOM_LEFT = "bottom-left"
    TOP_RIGHT = "top-right"
    TOP_LEFT = "top-left"


class ThemeConfig(BaseResponse):
    """Widget theme configuration (JSONB structure)."""

    primaryColor: str = Field("#3B82F6", description="Primary brand color (hex)")
    fontFamily: str = Field("Inter, sans-serif", description="Font family")
    borderRadius: str = Field("12px", description="Border radius")
    chatBubbleColor: str = Field("#3B82F6", description="Chat bubble background color")

    # Additional theme properties (optional)
    secondaryColor: Optional[str] = Field(None, description="Secondary color")
    backgroundColor: Optional[str] = Field(None, description="Chat background")
    textColor: Optional[str] = Field(None, description="Primary text color")


class WidgetConfigBase(BaseResponse):
    """Base widget configuration fields."""

    position: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = Field(
        "bottom-right", description="Widget position on page"
    )
    auto_open: bool = Field(False, description="Auto-open chat on page load")
    auto_open_delay: int = Field(3, ge=0, description="Delay before auto-open (seconds)")
    theme_config: ThemeConfig = Field(
        default_factory=ThemeConfig, description="Widget theme configuration"
    )
    greeting_message: str = Field(
        "Hi! How can I help you today?",
        description="Initial greeting message"
    )
    placeholder_text: str = Field(
        "Type your message...",
        description="Input placeholder text"
    )
    logo_url: Optional[str] = Field(None, description="Company logo URL")
    company_name: Optional[str] = Field(None, description="Company name for branding")
    allowed_domains: Optional[List[str]] = Field(
        None, description="Allowed domains (CORS), e.g., ['example.com']"
    )
    max_history_messages: int = Field(50, ge=1, le=200, description="Max chat history")
    show_confidence_scores: bool = Field(False, description="Show AI confidence scores")

    @field_validator("allowed_domains")
    @classmethod
    def validate_domains(cls, v):
        """Validate domain format (no protocol)."""
        if v is None:
            return v

        for domain in v:
            if "://" in domain:
                raise ValueError(f"Domain should not include protocol: {domain}")
            if " " in domain:
                raise ValueError(f"Domain should not contain spaces: {domain}")

        return v


class WidgetConfigResponse(WidgetConfigBase):
    """Full widget configuration response."""

    id: UUID
    customer_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WidgetConfigUpdateRequest(BaseRequest):
    """Request model for updating widget config (all fields optional)."""

    position: Optional[Literal["bottom-right", "bottom-left", "top-right", "top-left"]] = None
    auto_open: Optional[bool] = None
    auto_open_delay: Optional[int] = Field(None, ge=0)
    theme_config: Optional[ThemeConfig] = None
    greeting_message: Optional[str] = None
    placeholder_text: Optional[str] = None
    logo_url: Optional[str] = None
    company_name: Optional[str] = None
    allowed_domains: Optional[List[str]] = None
    max_history_messages: Optional[int] = Field(None, ge=1, le=200)
    show_confidence_scores: Optional[bool] = None

    @field_validator("allowed_domains")
    @classmethod
    def validate_domains(cls, v):
        """Validate domain format (no protocol)."""
        if v is None:
            return v

        for domain in v:
            if "://" in domain:
                raise ValueError(f"Domain should not include protocol: {domain}")
            if " " in domain:
                raise ValueError(f"Domain should not contain spaces: {domain}")

        return v


# ============================================================================
# Customer Details (with related data)
# ============================================================================

class CustomerDetailsResponse(CustomerBase):
    """
    Detailed customer response with related API keys and widget config.

    Includes full customer data plus related entities (JOIN).
    """

    id: UUID
    created_at: datetime
    updated_at: datetime

    # Related data (JOINed)
    api_keys: List[APIKeyBase] = Field(
        default_factory=list,
        description="Customer's API keys (no full keys)"
    )
    widget_config: Optional[WidgetConfigResponse] = Field(
        None,
        description="Widget configuration (null if not configured)"
    )

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Public Widget Config (by API key)
# ============================================================================

class WidgetConfigPublicResponse(WidgetConfigBase):
    """
    PUBLIC widget configuration response (fetched by API key).

    No sensitive data included (no IDs, no timestamps, no customer info).
    """

    # Explicitly excludes: id, customer_id, created_at, updated_at
    pass
