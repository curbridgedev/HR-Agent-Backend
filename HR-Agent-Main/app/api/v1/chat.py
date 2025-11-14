"""
Chat API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from app.models.chat import ChatRequest, ChatResponse, ChatStreamChunk, SessionsListResponse
from app.services.chat import process_chat, process_chat_stream, get_chat_history, get_sessions_list, clear_chat_session
from app.core.logging import get_logger
from app.core.dependencies import get_current_user_id

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message and return the agent's response.

    This is the main chat endpoint for non-streaming requests.

    Args:
        request: Chat request with message and session context

    Returns:
        Chat response with agent message, confidence score, and sources

    Raises:
        HTTPException: If processing fails
    """
    try:
        response = await process_chat(request)
        return response
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Process a chat message with streaming response.

    Returns Server-Sent Events (SSE) for real-time response streaming.

    Args:
        request: Chat request with message and session context

    Returns:
        StreamingResponse with SSE events
    """
    try:
        async def event_generator():
            """Generate SSE events from chat stream."""
            try:
                async for chunk in process_chat_stream(request):
                    # Format as SSE
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Stream generation error: {e}", exc_info=True)
                error_chunk = ChatStreamChunk(
                    chunk=f"Error: {str(e)}",
                    is_final=True,
                    confidence=0.0,
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    except Exception as e:
        logger.error(f"Chat stream endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    limit: int = 50,
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Retrieve chat history for a session.

    **Security**: Verifies session belongs to authenticated user before returning history.

    Args:
        session_id: Session identifier
        limit: Maximum number of messages to return (default: 50)
        current_user_id: Authenticated user ID (injected by dependency)

    Returns:
        Dict with session_id and messages list

    Raises:
        HTTPException: 401 if not authenticated, 403 if not authorized, 404 if not found
    """
    try:
        # Verify session belongs to authenticated user
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        session_check = (
            supabase.table("chat_sessions")
            .select("user_id")
            .eq("session_id", session_id)
            .execute()
        )

        if not session_check.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session_user_id = session_check.data[0].get("user_id")

        if session_user_id != current_user_id:
            logger.warning(
                f"Authorization failed: user {current_user_id} attempted to access "
                f"session {session_id} belonging to {session_user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied. You can only view your own chat sessions.",
            )

        # User is authorized, fetch history
        messages = await get_chat_history(session_id, limit)
        return {
            "session_id": session_id,
            "messages": messages,
            "count": len(messages),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")


@router.get("/sessions", response_model=SessionsListResponse)
async def list_sessions(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of sessions per page"),
    current_user_id: str = Depends(get_current_user_id),
) -> SessionsListResponse:
    """
    Get paginated list of chat sessions for authenticated user.

    Returns ONLY the authenticated user's sessions, sorted by most recent activity (updated_at DESC).

    **Security**: Automatically filters by authenticated user ID.

    Args:
        page: Page number (default: 1)
        page_size: Number of sessions per page (default: 50, max: 100)
        current_user_id: Authenticated user ID (injected by dependency)

    Returns:
        Paginated list of session summaries with metadata

    Raises:
        HTTPException: 401 if not authenticated, 500 if fetch fails
    """
    try:
        # CRITICAL: Always filter by authenticated user ID
        result = await get_sessions_list(page=page, page_size=page_size, user_id=current_user_id)
        return result
    except Exception as e:
        logger.error(f"Get sessions list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Delete a chat session and all its messages.

    **Security**: Verifies session belongs to authenticated user before deleting.

    Args:
        session_id: Session identifier
        current_user_id: Authenticated user ID (injected by dependency)

    Returns:
        Success confirmation

    Raises:
        HTTPException: 401 if not authenticated, 403 if not authorized, 404 if not found
    """
    try:
        # Delete session with authorization check
        success = await clear_chat_session(session_id, user_id=current_user_id)

        if success:
            return {
                "success": True,
                "message": f"Session {session_id} deleted successfully",
            }
        else:
            # If it returns False, could be not found OR authorization failed
            # check_chat_session handles authorization and returns False for both cases
            raise HTTPException(
                status_code=404,
                detail="Session not found or you don't have permission to delete it",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")
