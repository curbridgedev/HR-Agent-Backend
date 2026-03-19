"""
Analytics API endpoints for admin dashboard.

Provides aggregated analytics data including:
- Session counts and trends
- Deflection rate (% answered without escalation)
- Confidence score distribution over time
- Most frequently asked questions
"""

from typing import Optional, Literal
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_user_id
from app.core.logging import get_logger
from app.models.analytics import (
    SessionsAnalyticsResponse,
    DeflectionRateResponse,
    ConfidenceScoresResponse,
    TopQuestionsResponse,
    CitationRateResponse,
)
from app.services.analytics import (
    get_sessions_analytics,
    get_deflection_rate,
    get_confidence_scores,
    get_top_questions,
    get_citation_rate,
)

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user_id)])


# ============================================================================
# Session Analytics Endpoints
# ============================================================================

def _resolve_user_scope(scope: Optional[str], current_user_id: str) -> Optional[str]:
    """Return user_id to filter by when scope=user, else None for global."""
    return current_user_id if scope == "user" else None


def _parse_end_date_inclusive(end_date_str: str) -> datetime:
    """Parse end_date and return end of day so the full day is included in range."""
    dt = datetime.fromisoformat(end_date_str)
    # If date-only (no time), extend to end of day
    if end_date_str.strip() and "T" not in end_date_str.upper() and " " not in end_date_str:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


@router.get("/sessions", response_model=SessionsAnalyticsResponse)
async def get_sessions(
    current_user_id: str = Depends(get_current_user_id),
    period: Literal["daily", "weekly", "monthly", "all-time"] = Query(
        "daily",
        description="Aggregation period"
    ),
    start_date: Optional[str] = Query(
        None,
        description="Start date (ISO 8601 format, e.g., 2025-01-01)"
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date (ISO 8601 format, e.g., 2025-01-31)"
    ),
    scope: Optional[Literal["user", "org"]] = Query(
        None,
        description="Scope: 'user' for own data, 'org' or omit for global"
    )
):
    """
    Get session count aggregation for dashboard charts.

    Returns total session count and breakdown by date according to specified period.

    Args:
        period: Aggregation period (daily, weekly, monthly, all-time)
        start_date: Start date (defaults to 30 days ago if not provided)
        end_date: End date (defaults to now if not provided)

    Returns:
        Session analytics with total count and breakdown by period

    Example:
        GET /api/v1/analytics/sessions?period=daily
        GET /api/v1/analytics/sessions?period=weekly&start_date=2025-01-01&end_date=2025-01-31
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid start_date format: {start_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        if end_date:
            try:
                end_dt = _parse_end_date_inclusive(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid end_date format: {end_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        logger.info(f"Fetching session analytics: period={period}, start={start_date}, end={end_date}")

        user_id_filter = _resolve_user_scope(scope, current_user_id)
        analytics = await get_sessions_analytics(
            period=period,
            start_date=start_dt,
            end_date=end_dt,
            user_id=user_id_filter
        )

        return analytics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch session analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch session analytics: {str(e)}"
        )


# ============================================================================
# Deflection Rate Endpoint
# ============================================================================

@router.get("/deflection-rate", response_model=DeflectionRateResponse)
async def get_deflection_rate_endpoint(
    current_user_id: str = Depends(get_current_user_id),
    start_date: Optional[str] = Query(
        None,
        description="Start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date (ISO 8601 format)"
    ),
    include_daily: bool = Query(
        False,
        description="Include daily breakdown of deflection rates"
    ),
    scope: Optional[Literal["user", "org"]] = Query(
        None,
        description="Scope: 'user' for own data, 'org' or omit for global"
    )
):
    """
    Calculate deflection rate (percentage of queries answered without escalation).

    Deflection rate = (messages with confidence >= threshold) / total messages × 100

    Uses the current confidence threshold from agent configuration.

    Args:
        start_date: Start date (defaults to 30 days ago if not provided)
        end_date: End date (defaults to now if not provided)
        include_daily: Include daily breakdown (default: False)

    Returns:
        Deflection rate analysis with total/deflected/escalated message counts

    Example:
        GET /api/v1/analytics/deflection-rate
        GET /api/v1/analytics/deflection-rate?include_daily=true&start_date=2025-01-01
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid start_date format: {start_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        if end_date:
            try:
                end_dt = _parse_end_date_inclusive(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid end_date format: {end_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        logger.info(f"Calculating deflection rate: start={start_date}, end={end_date}")

        user_id_filter = _resolve_user_scope(scope, current_user_id)
        deflection_data = await get_deflection_rate(
            start_date=start_dt,
            end_date=end_dt,
            include_daily_breakdown=include_daily,
            user_id=user_id_filter
        )

        return deflection_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate deflection rate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate deflection rate: {str(e)}"
        )


# ============================================================================
# Confidence Scores Endpoint
# ============================================================================

@router.get("/confidence-scores", response_model=ConfidenceScoresResponse)
async def get_confidence_scores_endpoint(
    current_user_id: str = Depends(get_current_user_id),
    start_date: Optional[str] = Query(
        None,
        description="Start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date (ISO 8601 format)"
    ),
    granularity: Literal["hourly", "daily", "weekly"] = Query(
        "daily",
        description="Time series granularity"
    ),
    scope: Optional[Literal["user", "org"]] = Query(
        None,
        description="Scope: 'user' for own data, 'org' or omit for global"
    )
):
    """
    Get average confidence scores over time for performance tracking.

    Returns overall average, time series data, and distribution by confidence level.

    Args:
        start_date: Start date (defaults to 30 days ago if not provided)
        end_date: End date (defaults to now if not provided)
        granularity: Time granularity for time series (hourly, daily, weekly)

    Returns:
        Confidence score analysis with overall average, time series, and distribution

    Example:
        GET /api/v1/analytics/confidence-scores
        GET /api/v1/analytics/confidence-scores?granularity=weekly&start_date=2025-01-01
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid start_date format: {start_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        if end_date:
            try:
                end_dt = _parse_end_date_inclusive(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid end_date format: {end_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        logger.info(f"Fetching confidence scores: granularity={granularity}, start={start_date}, end={end_date}")

        user_id_filter = _resolve_user_scope(scope, current_user_id)
        confidence_data = await get_confidence_scores(
            start_date=start_dt,
            end_date=end_dt,
            granularity=granularity,
            user_id=user_id_filter
        )

        return confidence_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch confidence scores: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch confidence scores: {str(e)}"
        )


# ============================================================================
# Top Questions Endpoint
# ============================================================================

@router.get("/top-questions", response_model=TopQuestionsResponse)
async def get_top_questions_endpoint(
    current_user_id: str = Depends(get_current_user_id),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of top questions to return"
    ),
    start_date: Optional[str] = Query(
        None,
        description="Start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date (ISO 8601 format)"
    ),
    scope: Optional[Literal["user", "org"]] = Query(
        None,
        description="Scope: 'user' for own data, 'org' or omit for global"
    )
):
    """
    Get frequency analysis of user queries to identify common topics.

    Returns most frequently asked questions with their frequency counts
    and average confidence scores.

    Args:
        limit: Maximum number of questions to return (default: 10, max: 100)
        start_date: Start date (defaults to 30 days ago if not provided)
        end_date: End date (defaults to now if not provided)

    Returns:
        Top questions with frequency, average confidence, and last asked timestamp

    Example:
        GET /api/v1/analytics/top-questions
        GET /api/v1/analytics/top-questions?limit=20&start_date=2025-01-01
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid start_date format: {start_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        if end_date:
            try:
                end_dt = _parse_end_date_inclusive(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid end_date format: {end_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        logger.info(f"Fetching top questions: limit={limit}, start={start_date}, end={end_date}")

        user_id_filter = _resolve_user_scope(scope, current_user_id)
        top_questions_data = await get_top_questions(
            limit=limit,
            start_date=start_dt,
            end_date=end_dt,
            user_id=user_id_filter
        )

        return top_questions_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch top questions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch top questions: {str(e)}"
        )


# ============================================================================
# Citation Rate Endpoint
# ============================================================================

@router.get("/citation-rate", response_model=CitationRateResponse)
async def get_citation_rate_endpoint(
    current_user_id: str = Depends(get_current_user_id),
    start_date: Optional[str] = Query(
        None,
        description="Start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date (ISO 8601 format)"
    ),
    scope: Optional[Literal["user", "org"]] = Query(
        None,
        description="Scope: 'user' for own data, 'org' or omit for global"
    )
):
    """
    Calculate citation rate (percentage of responses with at least one source).

    Citation rate = (messages with metadata.sources_count > 0) / total assistant messages × 100

    Args:
        start_date: Start date (defaults to 30 days ago if not provided)
        end_date: End date (defaults to now if not provided)
        scope: Scope: 'user' for own data, 'org' or omit for global

    Returns:
        Citation rate analysis with total and messages_with_sources counts

    Example:
        GET /api/v1/analytics/citation-rate
        GET /api/v1/analytics/citation-rate?scope=user&start_date=2025-01-01
    """
    try:
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid start_date format: {start_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        if end_date:
            try:
                end_dt = _parse_end_date_inclusive(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid end_date format: {end_date}. Use ISO 8601 (YYYY-MM-DD)"
                )

        logger.info(f"Calculating citation rate: start={start_date}, end={end_date}")

        user_id_filter = _resolve_user_scope(scope, current_user_id)
        citation_data = await get_citation_rate(
            start_date=start_dt,
            end_date=end_dt,
            user_id=user_id_filter
        )

        return citation_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate citation rate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate citation rate: {str(e)}"
        )
