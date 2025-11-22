"""
Chat service business logic.
Handles chat requests, agent invocation, and response generation.
"""

import time
from typing import AsyncGenerator
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    SourceReference,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.utils.langfuse_client import create_callback_handler

logger = get_logger(__name__)


async def process_chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat request and generate a response.

    This is the main entry point for chat interactions.
    Flow:
    1. Invoke LangGraph agent (handles embedding, search, generation internally)
    2. Return response with confidence score

    Args:
        request: Chat request with message and context

    Returns:
        Chat response with message, confidence, and sources
    """
    start_time = time.time()

    try:
        logger.info(f"Processing chat request: session_id={request.session_id}")

        # Get province from session (locked in) or use request province for new sessions
        from app.db.supabase import get_supabase_client
        supabase = get_supabase_client()
        session_response = (
            supabase.table("chat_sessions")
            .select("province, message_count")
            .eq("session_id", request.session_id)
            .execute()
        )
        
        # Use session province if session exists and has messages, otherwise use request province
        if session_response.data and session_response.data[0].get("message_count", 0) > 0:
            # Session has messages - use locked province
            province = session_response.data[0].get("province", request.province or "MB")
            logger.debug(f"Using locked province from session: {province}")
        else:
            # New session - use request province or default
            province = request.province or "MB"
            logger.debug(f"Using province from request for new session: {province}")

        # Import agent graph
        from app.agents.graph import get_agent_graph

        # Retrieve conversation history for context
        conversation_history = await get_conversation_history_for_agent(request.session_id)

        # Prepare initial state
        initial_state = {
            "query": request.message,
            "session_id": request.session_id,
            "user_id": request.user_id,
            "province": province,  # Use session province (locked) or request province (new)
            "conversation_history": conversation_history,
            "context_documents": [],
            "context_text": "",
            "confidence_score": 0.0,
            "reasoning": "",
            "response": "",
            "sources": [],
            "escalated": False,
            "escalation_reason": None,
            "tokens_used": 0,
            "error": None,
        }

        # Create LangFuse callback handler for tracing
        langfuse_handler = create_callback_handler(
            session_id=request.session_id,
            user_id=request.user_id,
            tags=["chat", "agent"],
            metadata={
                "query": request.message,
                "platform": "api",  # ChatRequest doesn't have metadata field
            },
        )

        # Invoke agent graph with callback handler
        agent_graph = get_agent_graph()

        # Configure callbacks and metadata for LangFuse session tracking
        config = {}
        if langfuse_handler:
            config["callbacks"] = [langfuse_handler]
            config["metadata"] = {
                "langfuse_session_id": request.session_id,  # Group traces by session
                "langfuse_user_id": request.user_id,  # Track user across sessions
            }
            logger.debug(
                f"LangFuse tracing enabled: session={request.session_id}, user={request.user_id}"
            )

        final_state = await agent_graph.ainvoke(initial_state, config=config)

        # Convert sources to SourceReference objects
        sources = [
            SourceReference(
                content=source.get("content", ""),
                source=source.get("source", "unknown"),
                timestamp=source.get("timestamp"),
                metadata=source.get("metadata", {}),
                similarity_score=source.get("similarity_score", 0.0),
            )
            for source in final_state.get("sources", [])
        ]

        # Build response
        response = ChatResponse(
            message=final_state.get("response", ""),
            confidence=final_state.get("confidence_score", 0.0),
            sources=sources,
            escalated=final_state.get("escalated", False),
            escalation_reason=final_state.get("escalation_reason"),
            session_id=request.session_id,
            response_time_ms=int((time.time() - start_time) * 1000),
            tokens_used=final_state.get("tokens_used", 0),
        )

        # Flush LangFuse trace to ensure it's sent
        # Note: CallbackHandler automatically tracks tokens, costs, and latency
        # Additional metadata is captured in the initial handler creation
        if langfuse_handler:
            try:
                # Import flush utility
                from app.utils.langfuse_client import flush_langfuse
                flush_langfuse()
                logger.debug(
                    f"LangFuse trace flushed: session_id={request.session_id}, "
                    f"confidence={response.confidence:.2f}, tokens={response.tokens_used}"
                )
            except Exception as e:
                logger.error(f"Failed to flush LangFuse trace: {e}", exc_info=True)

        logger.info(
            f"Chat processed: session_id={request.session_id}, "
            f"confidence={response.confidence:.2f}, "
            f"escalated={response.escalated}, "
            f"response_time={response.response_time_ms}ms, "
            f"tokens={response.tokens_used}"
        )

        # Save user message and assistant response to database
        await save_chat_message(
            session_id=request.session_id,
            role="user",
            content=request.message,
            user_id=request.user_id,
            province=province,  # Use the province we determined (session or request)
            metadata={"platform": "api"},
        )

        await save_chat_message(
            session_id=request.session_id,
            role="assistant",
            content=response.message,
            confidence=response.confidence,
            escalated=response.escalated,
            user_id=request.user_id,
            province=province,  # Use the province we determined (session or request)
            metadata={
                "tokens_used": response.tokens_used,
                "response_time_ms": response.response_time_ms,
                "sources_count": len(response.sources),
            },
        )

        # Update session metadata (title, last_message, message_count)
        await update_session_metadata(request.session_id)

        return response

    except Exception as e:
        logger.error(f"Chat processing failed: {e}", exc_info=True)
        # Return error response instead of raising
        return ChatResponse(
            message="I apologize, but I encountered an error processing your request. Please try again.",
            confidence=0.0,
            sources=[],
            escalated=True,
            escalation_reason=f"System error: {str(e)}",
            session_id=request.session_id,
            response_time_ms=int((time.time() - start_time) * 1000),
        )


async def process_chat_stream(request: ChatRequest) -> AsyncGenerator[ChatStreamChunk, None]:
    """
    Process a chat request with streaming response.

    Yields response chunks as they are generated for real-time UX.
    Uses LangGraph's astream() to stream agent execution in real-time.

    Args:
        request: Chat request with message and context

    Yields:
        Chat stream chunks with partial responses
    """
    try:
        logger.info(f"Processing streaming chat request: session_id={request.session_id}")

        # Get province from session (locked in) or use request province for new sessions
        from app.db.supabase import get_supabase_client
        supabase = get_supabase_client()
        session_response = (
            supabase.table("chat_sessions")
            .select("province, message_count")
            .eq("session_id", request.session_id)
            .execute()
        )
        
        # Use session province if session exists and has messages, otherwise use request province
        if session_response.data and session_response.data[0].get("message_count", 0) > 0:
            # Session has messages - use locked province
            province = session_response.data[0].get("province", request.province or "MB")
            logger.debug(f"Using locked province from session: {province}")
        else:
            # New session - use request province or default
            province = request.province or "MB"
            logger.debug(f"Using province from request for new session: {province}")

        # Import agent graph
        from app.agents.graph import get_agent_graph

        # Retrieve conversation history for context
        conversation_history = await get_conversation_history_for_agent(request.session_id)

        # Prepare initial state
        initial_state = {
            "query": request.message,
            "session_id": request.session_id,
            "user_id": request.user_id,
            "province": province,  # Use session province (locked) or request province (new)
            "conversation_history": conversation_history,
            "context_documents": [],
            "context_text": "",
            "confidence_score": 0.0,
            "reasoning": "",
            "response": "",
            "sources": [],
            "escalated": False,
            "escalation_reason": None,
            "tokens_used": 0,
            "error": None,
        }

        # Create LangFuse callback handler for tracing
        langfuse_handler = create_callback_handler(
            session_id=request.session_id,
            user_id=request.user_id,
            tags=["chat", "agent", "streaming"],
            metadata={
                "query": request.message,
                "platform": "api",
            },
        )

        # Configure callbacks and metadata for LangFuse session tracking
        config = {}
        if langfuse_handler:
            config["callbacks"] = [langfuse_handler]
            config["metadata"] = {
                "langfuse_session_id": request.session_id,
                "langfuse_user_id": request.user_id,
            }

        # Get agent graph
        agent_graph = get_agent_graph()

        # Stream agent execution
        # We'll accumulate the response text and send it incrementally
        accumulated_response = ""
        final_state = {}  # Will merge all node outputs to get complete state

        async for chunk in agent_graph.astream(initial_state, config=config, stream_mode="updates"):
            # chunk is a dict with node updates
            # Format: {node_name: node_output_state}

            for node_name, node_output in chunk.items():
                logger.debug(f"Stream chunk from node: {node_name}")

                # If the generate_response node has output, stream the response
                if node_name == "generate_response" and "response" in node_output:
                    new_response = node_output.get("response", "")

                    # Calculate the delta (new content since last chunk)
                    if new_response and new_response != accumulated_response:
                        delta = new_response[len(accumulated_response):]
                        accumulated_response = new_response

                        # Yield the delta as a chunk
                        if delta:
                            yield ChatStreamChunk(
                                chunk=delta,
                                is_final=False,
                            )

                # Merge node output into final state to accumulate all state updates
                if node_output:
                    final_state.update(node_output)

        # After streaming completes, send final chunk with metadata
        if final_state:
            logger.info(
                f"Streaming complete: confidence={final_state.get('confidence_score', 0.0):.3f}, "
                f"method={final_state.get('confidence_method')}, "
                f"escalated={final_state.get('escalated', False)}"
            )

            # Convert sources to SourceReference objects
            sources = [
                SourceReference(
                    content=source.get("content", ""),
                    source=source.get("source", "unknown"),
                    timestamp=source.get("timestamp"),
                    metadata=source.get("metadata", {}),
                    similarity_score=source.get("similarity_score", 0.0),
                )
                for source in final_state.get("sources", [])
            ]

            # Send final chunk with confidence and sources
            final_chunk = ChatStreamChunk(
                chunk="",
                is_final=True,
                confidence=final_state.get("confidence_score", 0.0),
                sources=sources,
            )
            yield final_chunk

            # Save user message and assistant response to database
            await save_chat_message(
                session_id=request.session_id,
                role="user",
                content=request.message,
                user_id=request.user_id,
                province=province,  # Use the province we determined (session or request)
                metadata={"platform": "api", "streaming": True},
            )

            await save_chat_message(
                session_id=request.session_id,
                role="assistant",
                content=accumulated_response,
                confidence=final_state.get("confidence_score", 0.0),
                escalated=final_state.get("escalated", False),
                user_id=request.user_id,
                province=province,  # Use the province we determined (session or request)
                metadata={
                    "tokens_used": final_state.get("tokens_used", 0),
                    "sources_count": len(sources),
                    "streaming": True,
                },
            )

            # Update session metadata (title, last_message, message_count)
            await update_session_metadata(request.session_id)

            # Flush LangFuse trace
            if langfuse_handler:
                try:
                    from app.utils.langfuse_client import flush_langfuse
                    flush_langfuse()
                    logger.debug(f"LangFuse trace flushed for streaming session: {request.session_id}")
                except Exception as e:
                    logger.error(f"Failed to flush LangFuse trace: {e}", exc_info=True)

        logger.info(f"Streaming chat completed: session_id={request.session_id}")

    except Exception as e:
        logger.error(f"Streaming chat failed: {e}", exc_info=True)
        # Yield error chunk
        error_chunk = ChatStreamChunk(
            chunk=f"Error: {str(e)}",
            is_final=True,
            confidence=0.0,
        )
        yield error_chunk


async def ensure_chat_session(session_id: str, user_id: str = None, province: str = "MB") -> bool:
    """
    Ensure a chat session exists in the database.
    Creates the session if it doesn't exist.

    Args:
        session_id: Session identifier
        user_id: Optional user identifier
        province: Canadian province context (MB, ON, SK, AB, BC)

    Returns:
        True if session exists or was created successfully
    """
    try:
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        # Check if session exists
        response = (
            supabase.table("chat_sessions")
            .select("session_id")
            .eq("session_id", session_id)
            .execute()
        )

        if response.data:
            # Session exists - check if it has messages to lock province
            session_data = response.data[0]
            message_count = session_data.get("message_count", 0)
            
            # Only update province if session has no messages (new session)
            if province and message_count == 0:
                update_response = (
                    supabase.table("chat_sessions")
                    .update({"province": province})
                    .eq("session_id", session_id)
                    .execute()
                )
                if update_response.data:
                    logger.debug(f"Updated province for new session {session_id}: {province}")
            elif province and message_count > 0:
                # Session has messages - use existing province, don't update
                existing_province = session_data.get("province", "MB")
                logger.debug(
                    f"Session {session_id} has {message_count} messages - "
                    f"province locked to {existing_province}, ignoring update to {province}"
                )
            return True

        # Create new session
        # Note: 'active' is a generated column (computed from 'is_active')
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "is_active": True,
            "metadata": {},
            "province": province or "MB",  # Default to Manitoba
        }

        logger.debug(f"Attempting to create session with data: {session_data}")
        create_response = supabase.table("chat_sessions").insert(session_data).execute()

        if create_response.data:
            logger.info(f"Successfully created chat session: {session_id} with province: {province}")
            return True
        else:
            logger.error(f"Failed to create chat session: {session_id}, response: {create_response}")
            return False

    except Exception as e:
        logger.error(f"Error ensuring chat session {session_id}: {e}", exc_info=True)
        logger.error(f"Session data that failed: {session_data}")
        return False


async def update_session_metadata(session_id: str) -> bool:
    """
    Update session metadata (title, last_message, message_count).

    Called after saving messages to keep session metadata in sync.
    - title: First user message (truncated to 50 chars)
    - last_message: Most recent message (truncated to 100 chars)
    - message_count: Total messages in session

    Args:
        session_id: Session identifier

    Returns:
        True if updated successfully
    """
    try:
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        # Get first user message for title
        first_msg = (
            supabase.table("chat_messages")
            .select("content")
            .eq("session_id", session_id)
            .eq("role", "user")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )

        # Get last message (any role)
        last_msg = (
            supabase.table("chat_messages")
            .select("content")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        # Count total messages
        count_response = (
            supabase.table("chat_messages")
            .select("id", count="exact")
            .eq("session_id", session_id)
            .execute()
        )

        # Extract data
        title = "Untitled Conversation"
        if first_msg.data and first_msg.data[0].get("content"):
            content = first_msg.data[0]["content"]
            title = content[:50] + ("..." if len(content) > 50 else "")

        last_message = ""
        if last_msg.data and last_msg.data[0].get("content"):
            content = last_msg.data[0]["content"]
            last_message = content[:100] + ("..." if len(content) > 100 else "")

        message_count = count_response.count if count_response.count else 0

        # Update session metadata
        update_data = {
            "title": title,
            "last_message": last_message,
            "message_count": message_count,
            "updated_at": "NOW()",
        }

        response = (
            supabase.table("chat_sessions")
            .update(update_data)
            .eq("session_id", session_id)
            .execute()
        )

        if response.data:
            logger.debug(
                f"Updated session metadata: {session_id}, "
                f"title='{title[:30]}...', messages={message_count}"
            )
            return True
        else:
            logger.warning(f"Failed to update session metadata: {session_id}")
            return False

    except Exception as e:
        logger.error(f"Error updating session metadata: {e}", exc_info=True)
        return False


async def save_chat_message(
    session_id: str,
    role: str,
    content: str,
    confidence: float = None,
    escalated: bool = False,
    metadata: dict = None,
    user_id: str = None,
    province: str = "MB",
) -> bool:
    """
    Save a chat message to the database.

    Args:
        session_id: Session identifier
        role: Message role ('user', 'assistant', 'system')
        content: Message content
        confidence: Agent confidence score (for assistant messages)
        escalated: Whether the query was escalated
        metadata: Additional metadata
        user_id: Optional user identifier for session creation
        province: Canadian province context (MB, ON, SK, AB, BC)

    Returns:
        True if saved successfully
    """
    try:
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        # Ensure session exists first (to satisfy foreign key constraint)
        session_created = await ensure_chat_session(session_id, user_id, province)
        if not session_created:
            logger.error(f"Failed to ensure chat session exists: {session_id}")
            raise ValueError(f"Chat session {session_id} could not be created or found")

        # Prepare message data
        message_data = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "confidence": confidence,
            "escalated": escalated,
            "metadata": metadata or {},
            "province": province or "MB",  # Add province to message
        }

        # Insert message
        response = supabase.table("chat_messages").insert(message_data).execute()

        if response.data:
            logger.debug(f"Saved chat message: session={session_id}, role={role}, province={province}")
            return True
        else:
            logger.warning(f"Failed to save chat message: {response}")
            return False

    except Exception as e:
        logger.error(f"Error saving chat message: {e}", exc_info=True)
        return False


async def get_chat_history(session_id: str, limit: int = 50) -> list:
    """
    Retrieve chat history for a session from database.

    Args:
        session_id: Session identifier
        limit: Maximum number of messages to return

    Returns:
        List of chat messages with role, content, and metadata
    """
    try:
        logger.info(f"Retrieving chat history: session_id={session_id}, limit={limit}")

        # Import Supabase client
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        # Query chat_messages table
        response = (
            supabase.table("chat_messages")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=False)  # Oldest first for chronological order
            .limit(limit)
            .execute()
        )

        if not response.data:
            logger.info(f"No chat history found for session: {session_id}")
            return []

        # Format messages
        messages = [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["created_at"],
                "confidence": msg.get("confidence"),
                "escalated": msg.get("escalated", False),
                "metadata": msg.get("metadata", {}),
            }
            for msg in response.data
        ]

        logger.info(f"Retrieved {len(messages)} messages for session: {session_id}")
        return messages

    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}", exc_info=True)
        return []


async def get_conversation_history_for_agent(
    session_id: str,
    max_messages: int = None,
    max_tokens: int = None,
) -> list[dict]:
    """
    Retrieve and format conversation history for agent context.

    Implements sliding window based on message count and token limits.
    Returns most recent messages that fit within constraints.

    Args:
        session_id: Session identifier
        max_messages: Maximum number of messages to retrieve (from settings if None)
        max_tokens: Maximum tokens to allow in history (from settings if None)

    Returns:
        List of formatted messages for agent context (newest first for LLM context)
    """
    try:
        # Use settings defaults if not provided
        if max_messages is None:
            max_messages = settings.conversation_history_max_messages
        if max_tokens is None:
            max_tokens = settings.conversation_history_max_tokens

        # Check if conversation history is enabled
        if not settings.conversation_history_enabled:
            logger.debug("Conversation history disabled via settings")
            return []

        # Retrieve messages (chronological order from DB)
        all_messages = await get_chat_history(session_id, limit=max_messages)

        if not all_messages:
            logger.debug(f"No conversation history for session: {session_id}")
            return []

        # Filter to only user and assistant messages (exclude system messages)
        conversation_messages = [
            msg for msg in all_messages
            if msg["role"] in ["user", "assistant"]
        ]

        # Implement token-based sliding window
        # Estimate tokens: ~4 chars per token for English text
        selected_messages = []
        total_tokens = 0

        # Process messages in reverse (newest first) to stay within token limit
        for msg in reversed(conversation_messages):
            content = msg["content"]
            estimated_tokens = len(content) // 4  # Rough estimate

            # Check if adding this message would exceed token limit
            if total_tokens + estimated_tokens > max_tokens:
                logger.debug(
                    f"Reached token limit: {total_tokens}/{max_tokens} tokens, "
                    f"selected {len(selected_messages)}/{len(conversation_messages)} messages"
                )
                break

            selected_messages.insert(0, {
                "role": msg["role"],
                "content": msg["content"],
            })
            total_tokens += estimated_tokens

        logger.info(
            f"Retrieved {len(selected_messages)} conversation messages for agent "
            f"(~{total_tokens} tokens) from session {session_id}"
        )

        return selected_messages

    except Exception as e:
        logger.error(f"Failed to retrieve conversation history for agent: {e}", exc_info=True)
        return []


async def get_sessions_list(
    page: int = 1,
    page_size: int = 50,
    user_id: str = None,
) -> dict:
    """
    Get paginated list of chat sessions with metadata.

    Sessions are sorted by updated_at DESC (most recent first).

    Args:
        page: Page number (1-indexed)
        page_size: Number of sessions per page (max 100)
        user_id: Optional filter by user ID

    Returns:
        Dictionary with sessions list and pagination info
    """
    try:
        logger.info(f"Getting sessions list: page={page}, page_size={page_size}, user_id={user_id}")

        from app.db.supabase import get_supabase_client
        from app.models.chat import SessionSummary, SessionsListResponse
        import math

        supabase = get_supabase_client()

        # Validate and cap page_size
        page_size = min(page_size, 100)
        page = max(page, 1)  # Ensure page is at least 1

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query
        query = (
            supabase.table("chat_sessions")
            .select("session_id, title, last_message, message_count, province, created_at, updated_at", count="exact")
            .order("updated_at", desc=True)
        )

        # Add user_id filter if provided
        if user_id:
            query = query.eq("user_id", user_id)

        # Execute query with pagination
        response = query.range(offset, offset + page_size - 1).execute()

        # Get total count
        total = response.count if response.count else 0

        # Calculate total pages
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        # Convert to SessionSummary objects
        sessions = [
            SessionSummary(
                session_id=session["session_id"],
                title=session.get("title", "Untitled Conversation"),
                last_message=session.get("last_message", ""),
                message_count=session.get("message_count", 0),
                province=session.get("province", "MB"),
                created_at=session["created_at"],
                updated_at=session["updated_at"],
            )
            for session in response.data
        ]

        # Build response
        result = SessionsListResponse(
            sessions=sessions,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

        logger.info(
            f"Retrieved {len(sessions)} sessions: page={page}/{total_pages}, total={total}"
        )

        return result.model_dump()

    except Exception as e:
        logger.error(f"Failed to get sessions list: {e}", exc_info=True)
        # Return empty result on error
        from app.models.chat import SessionsListResponse

        return SessionsListResponse(
            sessions=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        ).model_dump()


async def clear_chat_session(session_id: str, user_id: str = None) -> bool:
    """
    Delete a chat session and all its messages.

    Args:
        session_id: Session identifier
        user_id: Optional user ID for authorization check

    Returns:
        True if session deleted successfully, False otherwise
    """
    try:
        logger.info(f"Deleting chat session: session_id={session_id}, user_id={user_id}")

        # Import Supabase client
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        # If user_id provided, verify session belongs to user (authorization check)
        if user_id:
            session_check = (
                supabase.table("chat_sessions")
                .select("user_id")
                .eq("session_id", session_id)
                .execute()
            )

            if not session_check.data:
                logger.warning(f"Session not found: {session_id}")
                return False

            if session_check.data[0].get("user_id") != user_id:
                logger.warning(
                    f"Authorization failed: user {user_id} attempted to delete "
                    f"session {session_id} belonging to {session_check.data[0].get('user_id')}"
                )
                return False

        # Delete all messages for this session
        delete_messages_response = (
            supabase.table("chat_messages")
            .delete()
            .eq("session_id", session_id)
            .execute()
        )

        # Delete the session record from chat_sessions table
        delete_session_response = (
            supabase.table("chat_sessions")
            .delete()
            .eq("session_id", session_id)
            .execute()
        )

        # Check if session was deleted
        if not delete_session_response.data:
            logger.warning(f"Session not found or already deleted: {session_id}")
            return False

        logger.info(
            f"Chat session deleted: session_id={session_id}, "
            f"messages_deleted={len(delete_messages_response.data) if delete_messages_response.data else 0}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to delete chat session: {e}", exc_info=True)
        return False


class ChatService:
    """
    Chat service for processing messages and generating responses.

    Provides a unified interface for chat operations across different platforms.
    """

    async def generate_response(
        self,
        query: str,
        user_id: str,
        session_id: str = None,
        metadata: dict = None,
    ) -> dict:
        """
        Generate AI response for a query.

        Args:
            query: User query/message
            user_id: User identifier
            session_id: Optional session ID (auto-generated if not provided)
            metadata: Optional metadata dict

        Returns:
            Dictionary with response, confidence, and sources
        """
        import uuid

        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        # Create chat request
        from app.models.chat import ChatRequest

        request = ChatRequest(
            message=query,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {},
        )

        # Process chat
        response = await process_chat(request)

        # Return as dictionary for easy consumption
        return {
            "response": response.message,
            "confidence": response.confidence,
            "sources": [
                {
                    "title": source.metadata.get("title", "Unknown"),
                    "content": source.content,
                    "similarity": source.similarity_score,
                    "source": source.source,
                }
                for source in response.sources
            ],
            "escalated": response.escalated,
            "session_id": response.session_id,
            "response_time_ms": response.response_time_ms,
        }


# Global service instance
_chat_service = None


def get_chat_service() -> ChatService:
    """Get or create global chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
