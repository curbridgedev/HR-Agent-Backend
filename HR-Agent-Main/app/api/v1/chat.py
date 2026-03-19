"""
Chat API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from app.models.chat import ChatRequest, ChatResponse, ChatStreamChunk, SessionsListResponse
from app.services.chat import (
    process_chat,
    process_chat_stream,
    get_chat_history,
    get_sessions_list,
    clear_chat_session,
    ensure_chat_session,
    save_chat_message,
    update_session_metadata,
)
from app.services.chat_attachments import upload_chat_attachment
from app.core.logging import get_logger
from app.core.dependencies import get_current_user_id

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user_id),
) -> ChatResponse:
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
        response = await process_chat(request, user_id_override=current_user_id)
        return response
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file (webm, mp4, mp3, wav, m4a)"),
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Transcribe audio to text using OpenAI Whisper.

    Accepts audio files in webm, mp4, mp3, wav, m4a formats (max 25MB).
    Used for voice input in the chat.
    """
    try:
        from openai import OpenAI
        from app.core.config import settings

        # Validate file size (25MB max for Whisper)
        content = await file.read()
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

        # Validate file type
        allowed_types = {"audio/webm", "audio/mp4", "audio/mpeg", "audio/mp3", "audio/wav", "audio/m4a", "audio/x-m4a"}
        content_type = file.content_type or ""
        if content_type not in allowed_types and not file.filename:
            # Infer from filename
            ext = (file.filename or "").lower().split(".")[-1]
            if ext not in ("webm", "mp4", "mp3", "wav", "m4a"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported format. Use: webm, mp4, mp3, wav, m4a",
                )

        client = OpenAI(api_key=settings.openai_api_key)

        # Create a file-like object for the API
        import io
        file_obj = io.BytesIO(content)
        file_obj.name = file.filename or "audio.webm"

        try:
            transcription = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",  # Better than whisper-1 for quiet/low-volume speech
                file=file_obj,
                response_format="json",
                language="en",  # Improves accuracy for English
                prompt="Transcription of voice input for HR assistant. User asking about employment standards.",  # Guides model
            )
        except Exception as e:
            if "gpt-4o-transcribe" in str(e).lower() or "model" in str(e).lower():
                logger.info(f"gpt-4o-transcribe unavailable, falling back to whisper-1: {e}")
                file_obj.seek(0)
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=file_obj,
                    response_format="json",
                    language="en",
                    prompt="Transcription of voice input for HR assistant. User asking about employment standards.",
                )
            else:
                raise

        return {"text": transcription.text, "transcript": transcription.text}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/stream/multipart")
async def chat_stream_multipart(
    message: str = Form(..., min_length=1, max_length=4000),
    session_id: str = Form(...),
    province: str = Form("ALL"),
    project_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    current_user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    """
    Process a chat message with file attachments and stream the response.

    Accepts multipart/form-data: message, session_id, province, project_id (optional), files (optional).
    Files are stored in Supabase Storage and linked to the user message.
    Returns SSE stream like /chat/stream.
    """
    try:
        # Ensure session exists
        await ensure_chat_session(
            session_id,
            user_id=current_user_id,
            province=province,
            project_id=project_id,
        )

        # Save user message first to get message_id for attachments
        msg_result = await save_chat_message(
            session_id=session_id,
            role="user",
            content=message,
            user_id=current_user_id,
            province=province,
            project_id=project_id,
        )
        if not msg_result:
            raise HTTPException(status_code=500, detail="Failed to save user message")
        message_id = str(msg_result) if isinstance(msg_result, str) else None

        # Upload files and link to message
        if message_id and files:
            for f in files:
                if not f.filename or f.filename.strip() == "":
                    continue
                try:
                    content = await f.read()
                    mime_type = f.content_type or None
                    await upload_chat_attachment(
                        file_content=content,
                        filename=f.filename,
                        mime_type=mime_type,
                        message_id=message_id,
                        session_id=session_id,
                        user_id=current_user_id,
                    )
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                except Exception as e:
                    logger.error(f"Failed to upload attachment {f.filename}: {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Failed to upload {f.filename}")

        # Build ChatRequest and stream
        request = ChatRequest(
            message=message,
            session_id=session_id,
            user_id=current_user_id,
            province=province,
            project_id=project_id,
        )

        async def event_generator():
            try:
                async for chunk in process_chat_stream(
                    request,
                    user_id_override=current_user_id,
                    user_message_already_saved=True,
                    attachment_message_id=message_id,
                ):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Multipart stream error: {e}", exc_info=True)
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
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat stream multipart error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
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
                async for chunk in process_chat_stream(request, user_id_override=current_user_id):
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
