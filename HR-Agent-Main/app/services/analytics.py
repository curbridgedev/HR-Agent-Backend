"""
Analytics service layer.

Business logic for analytics aggregation including sessions, deflection rates,
confidence scores, and top questions analysis.
"""

from typing import Optional, Literal
from datetime import datetime, timedelta
from supabase import Client

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.analytics import (
    SessionsAnalyticsResponse,
    SessionBreakdown,
    DateRange,
    DeflectionRateResponse,
    DeflectionBreakdown,
    ConfidenceScoresResponse,
    ConfidenceTimeSeries,
    ConfidenceDistribution,
    TopQuestionsResponse,
    TopQuestion,
)

logger = get_logger(__name__)


# ============================================================================
# Session Analytics
# ============================================================================

async def get_sessions_analytics(
    period: Literal["daily", "weekly", "monthly", "all-time"] = "daily",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Optional[Client] = None,
) -> SessionsAnalyticsResponse:
    """
    Get session count aggregation for dashboard charts.

    Args:
        period: Aggregation period (daily, weekly, monthly, all-time)
        start_date: Start date for analysis (defaults to 30 days ago)
        end_date: End date for analysis (defaults to now)
        db: Optional Supabase client

    Returns:
        Session analytics with total count and breakdown by date
    """
    if db is None:
        db = get_supabase_client()

    # Set default date range if not provided
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    try:
        logger.info(f"Fetching session analytics: period={period}, range={start_date} to {end_date}")

        # Query chat_sessions table with date aggregation
        if period == "all-time":
            # Get total count only
            total_response = db.table("chat_sessions").select(
                "id", count="exact"
            ).gte("created_at", start_date.isoformat()).lte(
                "created_at", end_date.isoformat()
            ).execute()

            total_sessions = total_response.count if total_response.count is not None else 0

            breakdown = [
                SessionBreakdown(
                    date=start_date.date().isoformat(),
                    session_count=total_sessions,
                    unique_users=None
                )
            ]

        else:
            # Use simple query and manual aggregation (no custom SQL functions needed)
            sessions_response = db.table("chat_sessions").select(
                "id,user_id,created_at"
            ).gte("created_at", start_date.isoformat()).lte(
                "created_at", end_date.isoformat()
            ).execute()

            # Manual aggregation by period
            from collections import defaultdict
            time_buckets = defaultdict(lambda: {"sessions": set(), "users": set()})

            for session in sessions_response.data:
                session_datetime = datetime.fromisoformat(
                    session["created_at"].replace("Z", "+00:00")
                )

                # Bucket by period
                if period == "daily":
                    bucket = session_datetime.date().isoformat()
                elif period == "weekly":
                    # Start of week (Monday)
                    week_start = session_datetime.date() - timedelta(days=session_datetime.weekday())
                    bucket = week_start.isoformat()
                else:  # monthly
                    bucket = session_datetime.date().replace(day=1).isoformat()

                time_buckets[bucket]["sessions"].add(session["id"])
                if session.get("user_id"):
                    time_buckets[bucket]["users"].add(session["user_id"])

            breakdown = [
                SessionBreakdown(
                    date=date,
                    session_count=len(counts["sessions"]),
                    unique_users=len(counts["users"]) if counts["users"] else None
                )
                for date, counts in sorted(time_buckets.items(), reverse=True)
            ]

            total_sessions = sum(b.session_count for b in breakdown)

        return SessionsAnalyticsResponse(
            period=period,
            total_sessions=total_sessions,
            date_range=DateRange(start=start_date, end=end_date),
            breakdown=breakdown
        )

    except Exception as e:
        logger.error(f"Failed to get session analytics: {e}", exc_info=True)
        raise


# ============================================================================
# Deflection Rate Analytics
# ============================================================================

async def get_deflection_rate(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    include_daily_breakdown: bool = False,
    db: Optional[Client] = None,
) -> DeflectionRateResponse:
    """
    Calculate deflection rate (percentage of queries answered without escalation).

    Deflection rate = (messages with confidence >= threshold) / total * 100

    Args:
        start_date: Start date for analysis (defaults to 30 days ago)
        end_date: End date for analysis (defaults to now)
        include_daily_breakdown: Include daily breakdown data
        db: Optional Supabase client

    Returns:
        Deflection rate analysis with total and escalated message counts
    """
    if db is None:
        db = get_supabase_client()

    # Set default date range
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    try:
        logger.info(f"Calculating deflection rate: range={start_date} to {end_date}")

        # Get current confidence threshold from agent config
        config_response = db.rpc(
            "get_active_config",
            {"config_name": "default_agent_config", "config_environment": "all"}
        ).execute()

        threshold = 0.95  # Default threshold
        if config_response.data and len(config_response.data) > 0:
            config_json = config_response.data[0]["config"]
            threshold = config_json.get("confidence_thresholds", {}).get("escalation", 0.95)

        # Query assistant messages with confidence scores
        messages_response = db.table("chat_messages").select(
            "confidence,created_at"
        ).eq("role", "assistant").not_.is_("confidence", "null").gte(
            "created_at", start_date.isoformat()
        ).lte("created_at", end_date.isoformat()).execute()

        if not messages_response.data:
            # No messages found
            return DeflectionRateResponse(
                deflection_rate=0.0,
                total_messages=0,
                deflected_messages=0,
                escalated_messages=0,
                date_range=DateRange(start=start_date, end=end_date),
                breakdown_by_day=None
            )

        total_messages = len(messages_response.data)
        deflected_messages = sum(
            1 for msg in messages_response.data
            if msg.get("confidence", 0) >= threshold
        )
        escalated_messages = total_messages - deflected_messages
        deflection_rate = (deflected_messages / total_messages * 100) if total_messages > 0 else 0.0

        # Daily breakdown if requested
        breakdown = None
        if include_daily_breakdown:
            from collections import defaultdict
            daily_stats = defaultdict(lambda: {"total": 0, "deflected": 0})

            for msg in messages_response.data:
                msg_date = datetime.fromisoformat(
                    msg["created_at"].replace("Z", "+00:00")
                ).date().isoformat()
                daily_stats[msg_date]["total"] += 1
                if msg.get("confidence", 0) >= threshold:
                    daily_stats[msg_date]["deflected"] += 1

            breakdown = [
                DeflectionBreakdown(
                    date=date,
                    deflection_rate=(stats["deflected"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
                )
                for date, stats in sorted(daily_stats.items(), reverse=True)
            ]

        return DeflectionRateResponse(
            deflection_rate=round(deflection_rate, 2),
            total_messages=total_messages,
            deflected_messages=deflected_messages,
            escalated_messages=escalated_messages,
            date_range=DateRange(start=start_date, end=end_date),
            breakdown_by_day=breakdown
        )

    except Exception as e:
        logger.error(f"Failed to calculate deflection rate: {e}", exc_info=True)
        raise


# ============================================================================
# Confidence Score Analytics
# ============================================================================

async def get_confidence_scores(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    granularity: Literal["hourly", "daily", "weekly"] = "daily",
    db: Optional[Client] = None,
) -> ConfidenceScoresResponse:
    """
    Get average confidence scores over time for performance tracking.

    Args:
        start_date: Start date for analysis (defaults to 30 days ago)
        end_date: End date for analysis (defaults to now)
        granularity: Time granularity (hourly, daily, weekly)
        db: Optional Supabase client

    Returns:
        Confidence score analysis with overall average, time series, and distribution
    """
    if db is None:
        db = get_supabase_client()

    # Set default date range
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    try:
        logger.info(f"Fetching confidence scores: granularity={granularity}, range={start_date} to {end_date}")

        # Query assistant messages with confidence scores
        messages_response = db.table("chat_messages").select(
            "confidence,created_at"
        ).eq("role", "assistant").not_.is_("confidence", "null").gte(
            "created_at", start_date.isoformat()
        ).lte("created_at", end_date.isoformat()).execute()

        if not messages_response.data:
            # No data
            return ConfidenceScoresResponse(
                overall_average=0.0,
                date_range=DateRange(start=start_date, end=end_date),
                time_series=[],
                distribution=ConfidenceDistribution(high=0.0, medium=0.0, low=0.0)
            )

        # Calculate overall average
        all_confidences = [msg["confidence"] for msg in messages_response.data]
        overall_average = sum(all_confidences) / len(all_confidences)

        # Calculate distribution
        high_count = sum(1 for c in all_confidences if c >= 0.95)
        medium_count = sum(1 for c in all_confidences if 0.85 <= c < 0.95)
        low_count = sum(1 for c in all_confidences if c < 0.85)
        total = len(all_confidences)

        distribution = ConfidenceDistribution(
            high=round(high_count / total * 100, 2),
            medium=round(medium_count / total * 100, 2),
            low=round(low_count / total * 100, 2)
        )

        # Time series aggregation
        from collections import defaultdict
        time_buckets = defaultdict(list)

        for msg in messages_response.data:
            msg_datetime = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))

            if granularity == "hourly":
                bucket = msg_datetime.replace(minute=0, second=0, microsecond=0)
            elif granularity == "daily":
                bucket = msg_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            else:  # weekly
                # Start of week (Monday)
                bucket = msg_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
                bucket = bucket - timedelta(days=bucket.weekday())

            time_buckets[bucket].append(msg["confidence"])

        time_series = [
            ConfidenceTimeSeries(
                timestamp=timestamp.isoformat(),
                average_confidence=round(sum(confidences) / len(confidences), 3),
                min_confidence=round(min(confidences), 3),
                max_confidence=round(max(confidences), 3),
                message_count=len(confidences)
            )
            for timestamp, confidences in sorted(time_buckets.items(), reverse=True)
        ]

        return ConfidenceScoresResponse(
            overall_average=round(overall_average, 3),
            date_range=DateRange(start=start_date, end=end_date),
            time_series=time_series,
            distribution=distribution
        )

    except Exception as e:
        logger.error(f"Failed to get confidence scores: {e}", exc_info=True)
        raise


# ============================================================================
# Top Questions Analytics
# ============================================================================

async def get_top_questions(
    limit: int = 10,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Optional[Client] = None,
) -> TopQuestionsResponse:
    """
    Get frequency analysis of user queries to identify common topics.

    Args:
        limit: Maximum number of top questions to return (default: 10)
        start_date: Start date for analysis (defaults to 30 days ago)
        end_date: End date for analysis (defaults to now)
        db: Optional Supabase client

    Returns:
        Top questions with frequency and average confidence
    """
    if db is None:
        db = get_supabase_client()

    # Set default date range
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    try:
        logger.info(f"Fetching top questions: limit={limit}, range={start_date} to {end_date}")

        # Query user messages with their corresponding assistant responses
        user_messages_response = db.table("chat_messages").select(
            "session_id,content,created_at"
        ).eq("role", "user").gte(
            "created_at", start_date.isoformat()
        ).lte("created_at", end_date.isoformat()).execute()

        if not user_messages_response.data:
            return TopQuestionsResponse(
                top_questions=[],
                total_unique_questions=0,
                date_range=DateRange(start=start_date, end=end_date)
            )

        # Get corresponding assistant responses for confidence scores
        assistant_messages_response = db.table("chat_messages").select(
            "session_id,confidence,created_at"
        ).eq("role", "assistant").gte(
            "created_at", start_date.isoformat()
        ).lte("created_at", end_date.isoformat()).execute()

        # Build session -> confidence mapping
        session_confidences = {}
        for msg in assistant_messages_response.data:
            session_id = msg["session_id"]
            if session_id not in session_confidences:
                session_confidences[session_id] = []
            if msg.get("confidence") is not None:
                session_confidences[session_id].append(msg["confidence"])

        # Aggregate questions by normalized content
        from collections import defaultdict
        question_stats = defaultdict(lambda: {
            "count": 0,
            "confidences": [],
            "last_asked": None
        })

        for msg in user_messages_response.data:
            # Normalize question (lowercase, strip whitespace)
            normalized = msg["content"].strip().lower()

            question_stats[normalized]["count"] += 1
            question_stats[normalized]["last_asked"] = msg["created_at"]

            # Add confidence scores from session
            session_id = msg["session_id"]
            if session_id in session_confidences:
                question_stats[normalized]["confidences"].extend(
                    session_confidences[session_id]
                )

        # Convert to TopQuestion objects and sort by frequency
        top_questions_list = []
        for question, stats in question_stats.items():
            avg_confidence = (
                sum(stats["confidences"]) / len(stats["confidences"])
                if stats["confidences"] else 0.0
            )

            top_questions_list.append(
                TopQuestion(
                    question=question[:200],  # Limit length for display
                    frequency=stats["count"],
                    avg_confidence=round(avg_confidence, 3),
                    last_asked_at=datetime.fromisoformat(
                        stats["last_asked"].replace("Z", "+00:00")
                    )
                )
            )

        # Sort by frequency and limit
        top_questions_list.sort(key=lambda x: x.frequency, reverse=True)
        top_questions_list = top_questions_list[:limit]

        return TopQuestionsResponse(
            top_questions=top_questions_list,
            total_unique_questions=len(question_stats),
            date_range=DateRange(start=start_date, end=end_date)
        )

    except Exception as e:
        logger.error(f"Failed to get top questions: {e}", exc_info=True)
        raise
