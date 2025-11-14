"""
Pydantic models for file upload and ingestion.
"""


from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response model for file upload operations."""

    status: str = Field(..., description="Upload status (success, error, partial)")
    message: str = Field(..., description="Status message")
    file_name: str = Field(..., description="Uploaded file name")
    messages_ingested: int = Field(0, description="Number of messages successfully ingested")
    messages_failed: int = Field(0, description="Number of messages that failed")
    errors: list[str] | None = Field(None, description="List of errors if any")


class ChatExportStats(BaseModel):
    """Statistics about a chat export."""

    total_messages: int = Field(..., description="Total messages parsed")
    unique_senders: int = Field(..., description="Number of unique senders")
    date_range_start: str | None = Field(None, description="Earliest message date")
    date_range_end: str | None = Field(None, description="Latest message date")
    platform: str = Field(..., description="Chat platform (whatsapp, telegram, slack)")
