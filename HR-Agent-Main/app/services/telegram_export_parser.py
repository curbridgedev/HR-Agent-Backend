"""
Telegram chat export parser for manual upload ingestion.

Telegram exports have the format:
[DD.MM.YY HH:MM:SS] Sender Name:
Message text (can be multiline)

Or for media messages:
[DD.MM.YY HH:MM:SS] Sender Name shared a photo
"""

import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.services.embedding import generate_embedding

logger = get_logger(__name__)


class TelegramExportParser:
    """Parser for Telegram chat export files."""

    def __init__(self) -> None:
        self.supabase = get_supabase_client()

        # Telegram export format: [DD.MM.YY HH:MM:SS] Sender Name:
        # Note: Telegram uses dots for dates and 24-hour time
        self.message_patterns = [
            # Pattern 1: [DD.MM.YY HH:MM:SS] Sender Name:
            re.compile(r"^\[(\d{2}\.\d{2}\.\d{2})\s+(\d{2}:\d{2}:\d{2})\]\s+([^:]+):\s*$"),
            # Pattern 2: [DD.MM.YYYY HH:MM:SS] Sender Name: (full year)
            re.compile(r"^\[(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2})\]\s+([^:]+):\s*$"),
        ]

        # Date formats for parsing
        self.date_formats = [
            "%d.%m.%y %H:%M:%S",  # 29.10.25 17:30:45
            "%d.%m.%Y %H:%M:%S",  # 29.10.2025 17:30:45
        ]

    async def parse_and_ingest(
        self,
        file_content: str,
        source_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Parse Telegram export file and ingest messages.

        Args:
            file_content: File content as string
            source_metadata: Source metadata (file_name, uploaded_by, etc.)

        Returns:
            Dict with ingestion results
        """
        try:
            # Parse messages
            messages = self._parse_export(file_content)

            if not messages:
                return {
                    "status": "error",
                    "message": "No messages found in export file",
                    "messages_found": 0,
                    "messages_ingested": 0,
                    "messages_failed": 0,
                }

            logger.info(f"Parsed {len(messages)} messages from Telegram export")

            # Ingest each message
            ingested = 0
            failed = 0
            errors = []

            for message in messages:
                try:
                    await self._ingest_message(message, source_metadata)
                    ingested += 1
                except Exception as e:
                    logger.error(f"Failed to ingest message: {e}")
                    failed += 1
                    errors.append(str(e))

            logger.info(f"Ingestion complete: {ingested} ingested, {failed} failed")

            return {
                "status": "success" if failed == 0 else "partial",
                "message": f"Ingested {ingested}/{len(messages)} messages",
                "messages_found": len(messages),
                "messages_ingested": ingested,
                "messages_failed": failed,
                "errors": errors[:10] if errors else None,  # Limit error list
            }

        except Exception as e:
            logger.error(f"Error parsing Telegram export: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to parse export: {str(e)}",
                "messages_found": 0,
                "messages_ingested": 0,
                "messages_failed": 0,
            }

    def _parse_export(self, content: str) -> list[dict[str, Any]]:
        """
        Parse Telegram export format into structured messages.

        Args:
            content: File content

        Returns:
            List of parsed message dicts
        """
        lines = content.split("\n")
        messages = []
        current_message = None

        for line in lines:
            # Try to match message header
            matched = False
            for pattern in self.message_patterns:
                match = pattern.match(line)
                if match:
                    # Save previous message if exists
                    if current_message:
                        text = current_message.get("text")
                        if text and isinstance(text, str) and text.strip():
                            messages.append(current_message)

                    # Start new message
                    raw_date, raw_time, sender = match.groups()

                    # Parse timestamp
                    timestamp = self._parse_timestamp(raw_date, raw_time)

                    current_message = {
                        "sender": sender.strip(),
                        "timestamp": timestamp.isoformat() if timestamp else None,
                        "raw_date": raw_date,
                        "raw_time": raw_time,
                        "text": "",
                    }

                    matched = True
                    break

            if not matched and current_message:
                # Continuation of current message (multiline)
                text_line = line.strip()
                if text_line:
                    # Skip system messages
                    if not self._is_system_message(text_line):
                        if current_message["text"]:
                            current_message["text"] += "\n" + text_line
                        else:
                            current_message["text"] = text_line

        # Add last message
        if current_message:
            text = current_message.get("text")
            if text and isinstance(text, str) and text.strip():
                messages.append(current_message)

        return messages

    def _parse_timestamp(self, raw_date: str, raw_time: str) -> datetime | None:
        """Parse date and time into datetime object."""
        datetime_str = f"{raw_date} {raw_time}"

        for fmt in self.date_formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue

        logger.warning(f"Failed to parse timestamp: {datetime_str}")
        return None

    def _is_system_message(self, text: str) -> bool:
        """
        Check if text is a Telegram system message.

        System messages include:
        - "joined the group"
        - "left the group"
        - "shared a photo"
        - "shared a video"
        - "changed group photo"
        - etc.
        """
        system_patterns = [
            "joined the group",
            "left the group",
            "shared a photo",
            "shared a video",
            "shared a file",
            "shared a voice message",
            "shared a location",
            "shared a contact",
            "shared a sticker",
            "changed group photo",
            "changed group name",
            "pinned a message",
            "unpinned a message",
            "invited",
            "removed",
            "Group created",
        ]

        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in system_patterns)

    async def _ingest_message(
        self, message: dict[str, Any], source_metadata: dict[str, Any]
    ) -> None:
        """
        Ingest a single parsed message into knowledge base.

        Args:
            message: Parsed message dict
            source_metadata: Source metadata (file_name, etc.)
        """
        # Extract content
        content = message["text"]
        sender = message["sender"]

        # Generate embedding for message
        embedding = await generate_embedding(content)

        # Create title from first 50 chars
        title = f"Telegram Export: {sender} - {content[:50]}..."

        # Prepare document for ingestion
        document = {
            "id": str(uuid4()),
            "title": title,
            "content": content,
            "embedding": embedding,
            "source": "telegram_export",
            "source_id": f"export_{source_metadata.get('file_name', 'unknown')}_{message.get('timestamp', 'unknown')}",
            "source_metadata": {
                "platform": "telegram",
                "sender": sender,
                "timestamp": message["timestamp"],
                "raw_date": message.get("raw_date"),
                "raw_time": message.get("raw_time"),
                "file_name": source_metadata.get("file_name"),
                "uploaded_by": source_metadata.get("uploaded_by"),
                "ingestion_type": "manual_export",
            },
            "metadata": {
                "uploaded_at": datetime.utcnow().isoformat(),
            },
            "processing_status": "completed",
        }

        # Store in Supabase
        self.supabase.table("documents").insert(document).execute()


# Singleton instance
_parser: TelegramExportParser | None = None


def get_telegram_export_parser() -> TelegramExportParser:
    """Get Telegram export parser singleton instance."""
    global _parser
    if _parser is None:
        _parser = TelegramExportParser()
    return _parser
