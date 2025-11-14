"""
Analytics API models for admin dashboard.

Pydantic models for analytics aggregation endpoints providing
session metrics, deflection rates, confidence scores, and top questions.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import Field, ConfigDict
from app.models.base import BaseResponse


# ============================================================================
# Common Models
# ============================================================================

class DateRange(BaseResponse):
    """Date range for analytics queries."""

    start: datetime = Field(..., description="Start date (ISO 8601)")
    end: datetime = Field(..., description="End date (ISO 8601)")


# ============================================================================
# Session Analytics Models
# ============================================================================

class SessionBreakdown(BaseResponse):
    """Session count breakdown by date."""

    date: str = Field(..., description="Date (ISO 8601 format)")
    session_count: int = Field(..., description="Number of sessions on this date")
    unique_users: Optional[int] = Field(None, description="Number of unique users (if available)")


class SessionsAnalyticsResponse(BaseResponse):
    """Response model for session count aggregation."""

    period: Literal["daily", "weekly", "monthly", "all-time"] = Field(
        ..., description="Aggregation period"
    )
    total_sessions: int = Field(..., description="Total number of sessions")
    date_range: DateRange = Field(..., description="Date range for this analysis")
    breakdown: List[SessionBreakdown] = Field(
        ..., description="Session count breakdown by date"
    )

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Deflection Rate Models
# ============================================================================

class DeflectionBreakdown(BaseResponse):
    """Daily deflection rate breakdown."""

    date: str = Field(..., description="Date (ISO 8601 format)")
    deflection_rate: float = Field(..., description="Deflection rate percentage (0-100)")


class DeflectionRateResponse(BaseResponse):
    """Response model for deflection rate analysis."""

    deflection_rate: float = Field(
        ..., description="Overall deflection rate percentage (0-100)"
    )
    total_messages: int = Field(..., description="Total assistant messages analyzed")
    deflected_messages: int = Field(
        ..., description="Messages with confidence >= threshold"
    )
    escalated_messages: int = Field(
        ..., description="Messages with confidence < threshold"
    )
    date_range: DateRange = Field(..., description="Date range for this analysis")
    breakdown_by_day: Optional[List[DeflectionBreakdown]] = Field(
        None, description="Daily deflection rate breakdown (optional)"
    )

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Confidence Score Models
# ============================================================================

class ConfidenceTimeSeries(BaseResponse):
    """Confidence score time series data point."""

    timestamp: str = Field(..., description="Timestamp (ISO 8601 format)")
    average_confidence: float = Field(..., description="Average confidence (0.0-1.0)")
    min_confidence: float = Field(..., description="Minimum confidence (0.0-1.0)")
    max_confidence: float = Field(..., description="Maximum confidence (0.0-1.0)")
    message_count: int = Field(..., description="Number of messages in this period")


class ConfidenceDistribution(BaseResponse):
    """Confidence score distribution by category."""

    high: float = Field(..., description="Percentage with confidence >= 0.95")
    medium: float = Field(..., description="Percentage with confidence 0.85-0.94")
    low: float = Field(..., description="Percentage with confidence < 0.85")


class ConfidenceScoresResponse(BaseResponse):
    """Response model for confidence score analysis."""

    overall_average: float = Field(
        ..., description="Overall average confidence (0.0-1.0)"
    )
    date_range: DateRange = Field(..., description="Date range for this analysis")
    time_series: List[ConfidenceTimeSeries] = Field(
        ..., description="Confidence scores over time"
    )
    distribution: ConfidenceDistribution = Field(
        ..., description="Distribution by confidence level"
    )

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Top Questions Models
# ============================================================================

class TopQuestion(BaseResponse):
    """Top question with frequency and confidence metrics."""

    question: str = Field(..., description="Normalized query text")
    frequency: int = Field(..., description="Number of times asked")
    avg_confidence: float = Field(..., description="Average response confidence (0.0-1.0)")
    last_asked_at: datetime = Field(..., description="Last time this question was asked")


class TopQuestionsResponse(BaseResponse):
    """Response model for top questions analysis."""

    top_questions: List[TopQuestion] = Field(
        ..., description="List of most frequently asked questions"
    )
    total_unique_questions: int = Field(
        ..., description="Total number of unique questions in period"
    )
    date_range: DateRange = Field(..., description="Date range for this analysis")

    model_config = ConfigDict(from_attributes=True)
