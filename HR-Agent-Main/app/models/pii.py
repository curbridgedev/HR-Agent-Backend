"""
PII (Personally Identifiable Information) models for detection and anonymization.

This module defines data models for PII detection results, anonymization operations,
and configuration of PII patterns.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PIIEntityType(str, Enum):
    """Standard PII entity types detected by the system."""

    EMAIL = "EMAIL_ADDRESS"
    PHONE = "PHONE_NUMBER"
    CREDIT_CARD = "CREDIT_CARD"
    PERSON = "PERSON"
    LOCATION = "LOCATION"
    DATE = "DATE_TIME"
    SSN = "US_SSN"
    IBAN = "IBAN_CODE"
    IP_ADDRESS = "IP_ADDRESS"
    URL = "URL"
    CUSTOM = "CUSTOM"


class AnonymizationStrategy(str, Enum):
    """Strategies for anonymizing PII."""

    REDACT = "redact"  # Remove completely
    REPLACE = "replace"  # Replace with placeholder
    MASK = "mask"  # Mask characters (e.g., ***-**-1234)
    HASH = "hash"  # One-way hash (for pseudonymization)
    KEEP = "keep"  # Keep original (for allowlisted entities)


class PIIDetectionResult(BaseModel):
    """Result of PII detection in text."""

    entity_type: PIIEntityType = Field(..., description="Type of PII detected")
    start: int = Field(..., description="Start position in text", ge=0)
    end: int = Field(..., description="End position in text", ge=0)
    score: float = Field(..., description="Confidence score", ge=0.0, le=1.0)
    text: str = Field(..., description="Original detected text")


class AnonymizationResult(BaseModel):
    """Result of anonymizing text containing PII."""

    original_text: str = Field(..., description="Original text before anonymization")
    anonymized_text: str = Field(..., description="Text after PII anonymization")
    entities_found: list[PIIDetectionResult] = Field(
        default_factory=list, description="List of PII entities detected"
    )
    anonymization_applied: bool = Field(
        ..., description="Whether any anonymization was performed"
    )
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class PIIPattern(BaseModel):
    """Custom PII pattern configuration."""

    name: str = Field(..., description="Pattern name", min_length=1, max_length=100)
    entity_type: str = Field(
        ..., description="Entity type label", min_length=1, max_length=50
    )
    pattern_type: str = Field(
        ...,
        description="Pattern matching type: regex, deny_list, or custom",
        pattern="^(regex|deny_list|custom)$",
    )
    pattern: str | list[str] = Field(
        ..., description="Regex pattern or list of values for deny_list"
    )
    score: float = Field(
        1.0, description="Confidence score for matches", ge=0.0, le=1.0
    )
    enabled: bool = Field(True, description="Whether pattern is active")


class PIIConfig(BaseModel):
    """Configuration for PII detection and anonymization."""

    enabled: bool = Field(True, description="Enable PII anonymization")
    default_strategy: AnonymizationStrategy = Field(
        AnonymizationStrategy.REPLACE, description="Default anonymization strategy"
    )
    redaction_placeholder: str = Field(
        "[REDACTED]", description="Placeholder text for redacted PII"
    )
    entity_strategies: dict[PIIEntityType, AnonymizationStrategy] = Field(
        default_factory=dict,
        description="Per-entity anonymization strategies (overrides default)",
    )
    custom_patterns: list[PIIPattern] = Field(
        default_factory=list, description="Custom PII detection patterns"
    )
    language: str = Field("en", description="Language for PII detection")
    min_score_threshold: float = Field(
        0.6, description="Minimum confidence score to consider PII", ge=0.0, le=1.0
    )


class PIIAuditLog(BaseModel):
    """Audit log entry for PII detection and anonymization operations."""

    id: UUID | None = Field(None, description="Audit log entry ID")
    document_id: UUID = Field(..., description="Document that was processed")
    operation: str = Field(..., description="Operation performed (detect, anonymize)")
    entities_detected: int = Field(..., description="Number of PII entities detected")
    entities_anonymized: int = Field(
        ..., description="Number of PII entities anonymized"
    )
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    performed_at: datetime = Field(
        default_factory=datetime.utcnow, description="When operation was performed"
    )
    performed_by: str | None = Field(
        None, description="User or system that performed the operation"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional operation metadata"
    )
