"""
Message normalization service for cross-platform data consistency.

This service converts messages from different sources (Slack, WhatsApp, Telegram, Admin Upload)
into a unified normalized format for consistent storage, deduplication, and retrieval.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.models.normalized_message import (
    DeduplicationResult,
    MessageSource,
    MessageType,
    NormalizedAuthor,
    NormalizedConversation,
    NormalizedMessage,
    NormalizedThread,
    NormalizationResult,
)

logger = logging.getLogger(__name__)


class MessageNormalizer:
    """
    Service for normalizing messages from different platforms into unified schema.

    Deduplication Strategy:
    - Merge if same content (content hash match)
    - Keep latest if edited (version management)
    """

    def __init__(self) -> None:
        self.supabase = get_supabase_client()

    def normalize_document(
        self, document: dict[str, Any], skip_deduplication: bool = False
    ) -> NormalizationResult:
        """
        Normalize a document from any source into the unified schema.

        Args:
            document: Raw document from Supabase documents table
            skip_deduplication: Skip deduplication check (for bulk operations)

        Returns:
            NormalizationResult with normalized message and deduplication info
        """
        source = document.get("source")

        try:
            # Route to source-specific normalizer
            if source == MessageSource.SLACK:
                normalized = self._normalize_slack(document)
            elif source in (MessageSource.WHATSAPP, MessageSource.WHATSAPP_EXPORT):
                normalized = self._normalize_whatsapp(document)
            elif source == MessageSource.TELEGRAM:
                normalized = self._normalize_telegram(document)
            elif source == MessageSource.ADMIN_UPLOAD:
                normalized = self._normalize_admin_upload(document)
            else:
                return NormalizationResult(
                    success=False,
                    error=f"Unknown source: {source}",
                )

            # Generate content hash for deduplication
            normalized.content_hash = self._generate_content_hash(normalized.content)

            # Check for duplicates unless skipped
            dedup_result = None
            if not skip_deduplication:
                dedup_result = self._check_duplicate(normalized)
                normalized.is_duplicate = dedup_result.is_duplicate
                normalized.duplicate_of = dedup_result.duplicate_of_id

            return NormalizationResult(
                success=True,
                normalized_message=normalized,
                deduplication_result=dedup_result,
            )

        except Exception as e:
            logger.error(f"Normalization failed for {source} document: {e}")
            return NormalizationResult(
                success=False,
                error=str(e),
            )

    def _normalize_slack(self, document: dict[str, Any]) -> NormalizedMessage:
        """Normalize Slack message into unified schema."""
        source_metadata = document.get("source_metadata", {})
        metadata = document.get("metadata", {})

        # Parse timestamp from message_ts (Unix timestamp with microseconds)
        message_ts = source_metadata.get("message_ts", "")
        timestamp = datetime.fromtimestamp(float(message_ts), tz=timezone.utc) if message_ts else datetime.now(timezone.utc)

        # Parse ingestion timestamp
        ingested_at_str = metadata.get("ingested_at")
        ingested_at = (
            datetime.fromisoformat(ingested_at_str.replace("Z", "+00:00"))
            if ingested_at_str
            else datetime.now(timezone.utc)
        )

        # Build normalized message
        return NormalizedMessage(
            id=UUID(document["id"]),
            source=MessageSource.SLACK,
            source_message_id=message_ts,
            source_id=document.get("source_id", ""),
            content=document.get("content", ""),
            message_type=MessageType.TEXT,
            timestamp=timestamp,
            ingested_at=ingested_at,
            author=NormalizedAuthor(
                id=source_metadata.get("user_id", "unknown"),
                name=None,  # Slack doesn't store username in metadata
                platform_username=None,
            ),
            conversation=NormalizedConversation(
                id=source_metadata.get("channel_id", "unknown"),
                name=source_metadata.get("channel_name"),
                type="channel",
            ),
            thread=NormalizedThread(
                parent_message_id=source_metadata.get("thread_ts"),
                is_thread_reply=source_metadata.get("is_thread_reply", False),
                thread_timestamp=source_metadata.get("thread_ts"),
            )
            if source_metadata.get("thread_ts")
            else None,
            platform_metadata={
                "team_id": source_metadata.get("team_id"),
                "channel_id": source_metadata.get("channel_id"),
                "message_ts": message_ts,
                "platform": "slack",
            },
            processing_status=document.get("processing_status", "completed"),
            embedding_generated=True,  # Assume embedding exists if document exists
        )

    def _normalize_whatsapp(self, document: dict[str, Any]) -> NormalizedMessage:
        """Normalize WhatsApp message into unified schema."""
        source_metadata = document.get("source_metadata", {})
        metadata = document.get("metadata", {})

        # Parse timestamp (can be ISO format or Unix epoch)
        timestamp_str = source_metadata.get("timestamp")
        if timestamp_str:
            try:
                # Try ISO format first
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                # Fall back to Unix epoch (from webhook)
                try:
                    timestamp = datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
                except (ValueError, TypeError):
                    timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        # Parse ingestion timestamp
        ingested_at_str = metadata.get("uploaded_at") or metadata.get("ingested_at")
        ingested_at = (
            datetime.fromisoformat(ingested_at_str.replace("Z", "+00:00"))
            if ingested_at_str
            else datetime.now(timezone.utc)
        )

        # Get author information (handle None values)
        author_id = source_metadata.get("from") or source_metadata.get("sender") or source_metadata.get("contact_wa_id") or "unknown"

        return NormalizedMessage(
            id=UUID(document["id"]),
            source=MessageSource.WHATSAPP if document["source"] == "whatsapp" else MessageSource.WHATSAPP_EXPORT,
            source_message_id=source_metadata.get("wamid", document.get("source_id", "")),
            source_id=document.get("source_id", ""),
            content=document.get("content", ""),
            message_type=MessageType.TEXT,
            timestamp=timestamp,
            ingested_at=ingested_at,
            author=NormalizedAuthor(
                id=author_id,
                name=source_metadata.get("sender") or source_metadata.get("contact_name"),
                platform_username=None,
            ),
            conversation=NormalizedConversation(
                id=source_metadata.get("phone_number_id", "unknown"),
                name=source_metadata.get("file_name", "WhatsApp Chat"),
                type="chat",
            ),
            thread=None,  # WhatsApp doesn't have threads
            platform_metadata={
                "platform": "whatsapp",
                "wamid": source_metadata.get("wamid"),
                "phone_number_id": source_metadata.get("phone_number_id"),
                "file_name": source_metadata.get("file_name"),
                "ingestion_type": source_metadata.get("ingestion_type"),
            },
            processing_status=document.get("processing_status", "completed"),
            embedding_generated=True,
        )

    def _normalize_telegram(self, document: dict[str, Any]) -> NormalizedMessage:
        """Normalize Telegram message into unified schema."""
        source_metadata = document.get("source_metadata", {})
        metadata = document.get("metadata", {})

        # Parse timestamp
        date_str = source_metadata.get("date")
        timestamp = (
            datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_str
            else datetime.now(timezone.utc)
        )

        # Parse ingestion timestamp
        ingested_at_str = metadata.get("ingested_at")
        ingested_at = (
            datetime.fromisoformat(ingested_at_str.replace("Z", "+00:00"))
            if ingested_at_str
            else datetime.now(timezone.utc)
        )

        return NormalizedMessage(
            id=UUID(document["id"]),
            source=MessageSource.TELEGRAM,
            source_message_id=str(source_metadata.get("message_id", "")),
            source_id=document.get("source_id", ""),
            content=document.get("content", ""),
            message_type=MessageType.TEXT,
            timestamp=timestamp,
            ingested_at=ingested_at,
            author=NormalizedAuthor(
                id=str(source_metadata.get("sender_id", "unknown")),
                name=source_metadata.get("sender_name"),
                platform_username=None,
            ),
            conversation=NormalizedConversation(
                id=str(source_metadata.get("chat_id", "unknown")),
                name=source_metadata.get("chat_name"),
                type="chat" if not source_metadata.get("is_channel") else "channel",
            ),
            thread=NormalizedThread(
                parent_message_id=str(source_metadata.get("reply_to_msg_id"))
                if source_metadata.get("reply_to_msg_id")
                else None,
                is_thread_reply=source_metadata.get("is_reply", False),
                thread_timestamp=None,
            )
            if source_metadata.get("is_reply")
            else None,
            platform_metadata={
                "platform": "telegram",
                "chat_id": source_metadata.get("chat_id"),
                "message_id": source_metadata.get("message_id"),
                "is_forwarded": source_metadata.get("is_forwarded"),
                "ingestion_type": source_metadata.get("ingestion_type"),
            },
            processing_status=document.get("processing_status", "completed"),
            embedding_generated=True,
        )

    def _normalize_admin_upload(self, document: dict[str, Any]) -> NormalizedMessage:
        """Normalize admin-uploaded document into unified schema."""
        source_metadata = document.get("source_metadata", {})
        metadata = document.get("metadata", {})

        # Admin uploads use created_at timestamp
        created_at_str = document.get("created_at")
        timestamp = (
            datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at_str
            else datetime.now(timezone.utc)
        )

        # Generate source_id and source_message_id from document id if not present
        doc_id = str(document["id"])
        source_id = document.get("source_id") or doc_id
        source_message_id = source_id

        return NormalizedMessage(
            id=UUID(document["id"]),
            source=MessageSource.ADMIN_UPLOAD,
            source_message_id=source_message_id,
            source_id=source_id,
            content=document.get("content", ""),
            message_type=MessageType.DOCUMENT,
            timestamp=timestamp,
            ingested_at=timestamp,
            author=NormalizedAuthor(
                id="admin",
                name="Administrator",
                platform_username=None,
            ),
            conversation=NormalizedConversation(
                id="admin_upload",
                name="Admin Uploads",
                type="system",
            ),
            thread=None,
            platform_metadata={
                "platform": "admin_upload",
                "original_file": source_metadata.get("original_file"),
                "file_type": metadata.get("file_type"),
                "chunk_index": source_metadata.get("chunk_index"),
                "total_chunks": source_metadata.get("total_chunks"),
                "parent_document_id": source_metadata.get("parent_document_id"),
            },
            processing_status=document.get("processing_status", "completed"),
            embedding_generated=True,
        )

    def _generate_content_hash(self, content: str) -> str:
        """
        Generate SHA-256 hash of content for deduplication.

        Args:
            content: Message content

        Returns:
            Hexadecimal SHA-256 hash
        """
        # Normalize content: lowercase, strip whitespace, remove extra spaces
        normalized_content = " ".join(content.lower().strip().split())
        return hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

    def _check_duplicate(self, message: NormalizedMessage) -> DeduplicationResult:
        """
        Check if message is a duplicate based on content hash.

        Deduplication Strategy:
        1. Same content hash = merge (mark as duplicate)
        2. Same source_id but different content = edited (keep latest)

        Uses indexed content_hash column for O(1) lookup performance.

        Args:
            message: Normalized message to check

        Returns:
            DeduplicationResult with duplicate detection info
        """
        try:
            # Check for exact content match using indexed content_hash column
            # This is MUCH faster than scanning all documents
            content_match_response = (
                self.supabase.table("documents")
                .select("id, source, source_id, created_at, content_hash")
                .eq("content_hash", message.content_hash)
                .neq("id", str(message.id))  # Exclude current document
                .limit(1)  # We only need to find one duplicate
                .execute()
            )

            if content_match_response.data and len(content_match_response.data) > 0:
                doc = content_match_response.data[0]
                logger.info(
                    f"Found duplicate content: {message.id} matches {doc['id']}"
                )
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_of_id=UUID(doc["id"]),
                    match_type="exact_content",
                    confidence=1.0,
                    content_hash=message.content_hash,
                )

            # Check for edited version (same source_id, different content)
            if message.source_id:
                edit_response = (
                    self.supabase.table("documents")
                    .select("id, source_id, content_hash, created_at")
                    .eq("source_id", message.source_id)
                    .neq("id", str(message.id))
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )

                if edit_response.data:
                    original = edit_response.data[0]
                    original_hash = original.get("content_hash")

                    # If content_hash is different, this is an edited version
                    if original_hash and original_hash != message.content_hash:
                        logger.info(
                            f"Detected edit: {message.source_id} has new version {message.id}"
                        )
                        return DeduplicationResult(
                            is_duplicate=False,  # Not a duplicate, it's an edited version
                            duplicate_of_id=UUID(original["id"]),
                            match_type="edited_version",
                            confidence=1.0,
                            content_hash=message.content_hash,
                        )

            # No duplicate found
            return DeduplicationResult(
                is_duplicate=False,
                content_hash=message.content_hash,
            )

        except Exception as e:
            logger.error(f"Deduplication check failed: {e}")
            # On error, assume not duplicate (fail open)
            return DeduplicationResult(
                is_duplicate=False,
                content_hash=message.content_hash,
            )

    async def normalize_and_store(
        self, document: dict[str, Any]
    ) -> NormalizationResult:
        """
        Normalize a document and update it in Supabase with normalized metadata.

        Args:
            document: Raw document from Supabase

        Returns:
            NormalizationResult with normalization and deduplication info
        """
        result = self.normalize_document(document)

        if not result.success or not result.normalized_message:
            return result

        normalized = result.normalized_message

        try:
            # Update document with normalized data in proper columns
            update_data = {
                # Store in dedicated columns for efficient querying
                "content_hash": normalized.content_hash,
                "is_duplicate": normalized.is_duplicate,
                "duplicate_of": str(normalized.duplicate_of) if normalized.duplicate_of else None,
                "author_id": normalized.author.id,
                "author_name": normalized.author.name,
                "conversation_id": normalized.conversation.id,
                "conversation_name": normalized.conversation.name,
                "normalized_timestamp": normalized.timestamp.isoformat(),
                "is_normalized": True,
                # Also keep in metadata for backward compatibility
                "metadata": {
                    **document.get("metadata", {}),
                    "normalized": True,
                    "normalized_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            self.supabase.table("documents").update(update_data).eq(
                "id", str(normalized.id)
            ).execute()

            logger.info(f"Successfully normalized and stored document {normalized.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to store normalized document: {e}")
            result.warnings.append(f"Storage failed: {e}")
            return result


def get_normalizer() -> MessageNormalizer:
    """Get MessageNormalizer instance."""
    return MessageNormalizer()
