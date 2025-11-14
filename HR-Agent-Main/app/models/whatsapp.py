"""
Pydantic models for WhatsApp Business API webhooks.

Based on official WhatsApp Cloud API documentation:
https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks
"""

from pydantic import BaseModel, Field

# ============================================================================
# Webhook Verification (GET request)
# ============================================================================


class WhatsAppVerification(BaseModel):
    """
    WhatsApp webhook verification request.

    Sent by WhatsApp during webhook URL setup to verify endpoint ownership.
    """

    mode: str = Field(..., alias="hub.mode", description="Should be 'subscribe'")
    verify_token: str = Field(..., alias="hub.verify_token", description="Verification token")
    challenge: str = Field(..., alias="hub.challenge", description="Challenge string to echo back")


# ============================================================================
# Webhook Event Models (POST request)
# ============================================================================


class WhatsAppProfile(BaseModel):
    """Contact profile information."""

    name: str = Field(..., description="Contact's display name")


class WhatsAppContact(BaseModel):
    """Contact information from webhook."""

    profile: WhatsAppProfile
    wa_id: str = Field(..., description="WhatsApp ID (phone number)")


class WhatsAppMetadata(BaseModel):
    """Metadata about the business phone number."""

    display_phone_number: str = Field(..., description="Business display phone number")
    phone_number_id: str = Field(..., description="Business phone number ID")


class WhatsAppTextMessage(BaseModel):
    """Text message content."""

    body: str = Field(..., description="Message text content")


class WhatsAppReaction(BaseModel):
    """Reaction to a message."""

    emoji: str = Field(..., description="Emoji used for reaction")
    message_id: str = Field(..., description="ID of message being reacted to")


class WhatsAppContext(BaseModel):
    """Context information for replies."""

    from_: str = Field(..., alias="from", description="Original sender")
    id: str = Field(..., description="Original message ID")


class WhatsAppError(BaseModel):
    """Error information."""

    code: int = Field(..., description="Error code")
    title: str = Field(..., description="Error title")
    details: str = Field(..., description="Error details")


class WhatsAppMessage(BaseModel):
    """
    WhatsApp message object.

    Supports multiple message types: text, image, document, audio, video, etc.
    """

    from_: str = Field(..., alias="from", description="Sender's phone number")
    id: str = Field(..., description="Message ID (wamid)")
    timestamp: str = Field(..., description="Unix timestamp")
    type: str = Field(..., description="Message type (text, reaction, image, etc.)")

    # Optional fields based on message type
    text: WhatsAppTextMessage | None = Field(None, description="Text message content")
    reaction: WhatsAppReaction | None = Field(None, description="Reaction content")
    context: WhatsAppContext | None = Field(None, description="Reply context")
    errors: list[WhatsAppError] | None = Field(None, description="Error information")


class WhatsAppConversationOrigin(BaseModel):
    """Origin of the conversation."""

    type: str = Field(..., description="Origin type (user_initiated, business_initiated, etc.)")


class WhatsAppConversation(BaseModel):
    """Conversation metadata."""

    id: str = Field(..., description="Conversation ID")
    expiration_timestamp: str | None = Field(None, description="Expiration timestamp")
    origin: WhatsAppConversationOrigin | None = Field(None, description="Conversation origin")


class WhatsAppPricing(BaseModel):
    """Pricing information for messages."""

    pricing_model: str = Field(..., description="Pricing model (CBP)")
    billable: bool = Field(..., description="Whether message is billable")
    category: str = Field(..., description="Message category (user_initiated, etc.)")


class WhatsAppStatus(BaseModel):
    """Message status update."""

    id: str = Field(..., description="Message ID")
    recipient_id: str = Field(..., description="Recipient phone number")
    status: str = Field(..., description="Status (sent, delivered, read, failed)")
    timestamp: str = Field(..., description="Status timestamp")
    conversation: WhatsAppConversation | None = Field(None, description="Conversation metadata")
    pricing: WhatsAppPricing | None = Field(None, description="Pricing information")


class WhatsAppValue(BaseModel):
    """
    Value object containing the core webhook data.

    Contains either messages (incoming) or statuses (outgoing updates).
    """

    messaging_product: str = Field(..., description="Always 'whatsapp'")
    metadata: WhatsAppMetadata = Field(..., description="Phone number metadata")
    contacts: list[WhatsAppContact] | None = Field(None, description="Contact information")

    # Either messages OR statuses will be present
    messages: list[WhatsAppMessage] | None = Field(None, description="Incoming messages")
    statuses: list[WhatsAppStatus] | None = Field(None, description="Outgoing message statuses")


class WhatsAppChange(BaseModel):
    """Change object containing the event data."""

    value: WhatsAppValue = Field(..., description="Event value")
    field: str = Field(..., description="Field that changed (always 'messages')")


class WhatsAppEntry(BaseModel):
    """Entry object containing changes."""

    id: str = Field(..., description="WhatsApp Business Account ID")
    changes: list[WhatsAppChange] = Field(..., description="List of changes")


class WhatsAppWebhookEvent(BaseModel):
    """
    Root webhook event object.

    This is the top-level structure for all WhatsApp webhook notifications.
    """

    object: str = Field(..., description="Object type (always 'whatsapp_business_account')")
    entry: list[WhatsAppEntry] = Field(..., description="List of entries")


# ============================================================================
# Response Models
# ============================================================================


class WhatsAppWebhookResponse(BaseModel):
    """Response model for webhook processing."""

    status: str = Field(..., description="Processing status (success, error, ignored)")
    message: str = Field(..., description="Status message")
    event_id: str | None = Field(None, description="Event ID if available")
    response_sent: bool = Field(False, description="Whether a response was sent to WhatsApp")
