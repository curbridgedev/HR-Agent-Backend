"""
Parser service for WhatsApp chat exports.

Handles parsing of WhatsApp chat export files (.txt format) and ingestion into knowledge base.
"""

import re
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client

logger = get_logger(__name__)


class WhatsAppExportParser:
    """Parser for WhatsApp chat export files."""

    def __init__(self) -> None:
        self.supabase = get_supabase_client()

        # Regex patterns for WhatsApp export formats
        # Supports multiple international formats, brackets vs. no brackets, with/without seconds
        self.patterns = [
            # === NO BRACKETS FORMAT (Android/newer versions) ===
            # Pattern 1: DD/MM/YYYY, H:MM am/pm - Contact: Message (most common modern format)
            re.compile(
                r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}\s+[ap]m)\s+-\s+([^:]+):\s+(.+)$",
                re.IGNORECASE,
            ),
            # Pattern 2: DD/MM/YY, HH:MM - Contact: Message (24-hour, no seconds, no brackets)
            re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2})\s+-\s+([^:]+):\s+(.+)$"),
            # Pattern 3: DD/MM/YYYY, HH:MM:SS - Contact: Message (24-hour with seconds, no brackets)
            re.compile(
                r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}:\d{2})\s+-\s+([^:]+):\s+(.+)$"
            ),
            # Pattern 4: DD.MM.YY, HH:MM - Contact: Message (European format, no brackets)
            re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{2,4}),\s+(\d{1,2}:\d{2})\s+-\s+([^:]+):\s+(.+)$"),
            # Pattern 5: DD-MM-YYYY, HH:MM - Contact: Message (dash separator, no brackets)
            re.compile(r"^(\d{1,2}-\d{1,2}-\d{2,4}),\s+(\d{1,2}:\d{2})\s+-\s+([^:]+):\s+(.+)$"),
            # === WITH BRACKETS FORMAT (iOS/older versions) ===
            # Pattern 6: [DD/MM/YYYY, HH:MM:SS] Contact: Message
            re.compile(
                r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}:\d{2}(?:\s+[AP]M)?)\]\s+([^:]+):\s+(.+)$"
            ),
            # Pattern 7: [DD/MM/YYYY, H:MM am/pm] Contact: Message
            re.compile(
                r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}\s+[AP]M)\]\s+([^:]+):\s+(.+)$",
                re.IGNORECASE,
            ),
            # Pattern 8: [DD.MM.YY, HH:MM:SS] Contact: Message (European with brackets)
            re.compile(
                r"^\[(\d{1,2}\.\d{1,2}\.\d{2,4}),?\s+(\d{1,2}:\d{2}:\d{2})\]\s+([^:]+):\s+(.+)$"
            ),
            # Pattern 9: [DD-MM-YYYY, HH:MM] Contact: Message (dash separator with brackets)
            re.compile(r"^\[(\d{1,2}-\d{1,2}-\d{2,4}),?\s+(\d{1,2}:\d{2})\]\s+([^:]+):\s+(.+)$"),
            # === US FORMAT ===
            # Pattern 10: MM/DD/YYYY, H:MM AM/PM - Contact: Message (US format no brackets)
            re.compile(
                r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}\s+[AP]M)\s+-\s+([^:]+):\s+(.+)$"
            ),
        ]

    async def parse_and_ingest(
        self, file_content: str, source_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Parse WhatsApp chat export and ingest into knowledge base.

        Args:
            file_content: Content of the WhatsApp export file
            source_metadata: Additional metadata (file_name, uploaded_by, etc.)

        Returns:
            Dict with ingestion statistics
        """
        try:
            # Parse messages from export
            messages = self._parse_export(file_content)

            if not messages:
                return {
                    "status": "error",
                    "message": "No messages found in export file",
                    "messages_ingested": 0,
                    "messages_failed": 0,
                }

            # Ingest messages into knowledge base
            ingested_count = 0
            failed_count = 0
            errors: list[str] = []

            for message in messages:
                try:
                    await self._ingest_message(message, source_metadata)
                    ingested_count += 1
                except Exception as e:
                    failed_count += 1
                    error_msg = f"Failed to ingest message from {message.get('sender')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Calculate stats
            unique_senders = len({msg["sender"] for msg in messages})
            dates = [msg["timestamp"] for msg in messages if msg.get("timestamp") is not None]
            date_range_start = min(dates) if dates else None
            date_range_end = max(dates) if dates else None

            return {
                "status": "success" if failed_count == 0 else "partial",
                "message": f"Ingested {ingested_count}/{len(messages)} messages",
                "messages_ingested": ingested_count,
                "messages_failed": failed_count,
                "errors": errors if errors else None,
                "stats": {
                    "total_messages": len(messages),
                    "unique_senders": unique_senders,
                    "date_range_start": date_range_start,
                    "date_range_end": date_range_end,
                    "platform": "whatsapp",
                },
            }

        except Exception as e:
            logger.error(f"Error parsing WhatsApp export: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "messages_ingested": 0,
                "messages_failed": 0,
            }

    def _parse_export(self, content: str) -> list[dict[str, Any]]:
        """
        Parse WhatsApp export content into structured messages.

        Args:
            content: Raw export file content

        Returns:
            List of parsed messages
        """
        messages: list[dict[str, Any]] = []
        current_message: dict[str, Any] | None = None

        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Try to match as new message
            matched = False
            for pattern in self.patterns:
                match = pattern.match(line)
                if match:
                    # Save previous message if exists
                    if current_message:
                        messages.append(current_message)

                    # Parse new message
                    date_str, time_str, sender, text = match.groups()

                    # Parse timestamp
                    timestamp = self._parse_timestamp(date_str, time_str)

                    current_message = {
                        "sender": sender.strip(),
                        "text": text.strip(),
                        "timestamp": timestamp,
                        "raw_date": date_str,
                        "raw_time": time_str,
                    }
                    matched = True
                    break

            # If no match, append to current message (multi-line message)
            if not matched and current_message:
                current_message["text"] += "\n" + line

        # Add last message
        if current_message:
            messages.append(current_message)

        # Filter out system messages
        messages = [msg for msg in messages if not self._is_system_message(msg.get("text", ""))]

        logger.info(f"Parsed {len(messages)} messages from WhatsApp export")
        return messages

    def _parse_timestamp(self, date_str: str, time_str: str) -> str | None:
        """
        Parse date and time strings to ISO format.

        Args:
            date_str: Date string (e.g., "29/10/2025" or "10/29/25")
            time_str: Time string (e.g., "17:30:45" or "5:30:45 PM")

        Returns:
            ISO format timestamp or None if parsing fails
        """
        try:
            # Clean up time string (remove extra spaces)
            time_str = time_str.strip()

            # Try different date formats (ordered by most common first)
            date_formats = [
                "%d/%m/%Y",  # 29/10/2025 (most common)
                "%d/%m/%y",  # 29/10/25
                "%m/%d/%Y",  # 10/29/2025 (US format)
                "%m/%d/%y",  # 10/29/25 (US format)
                "%d.%m.%Y",  # 29.10.2025 (European)
                "%d.%m.%y",  # 29.10.25 (European)
                "%d-%m-%Y",  # 29-10-2025 (dash separator)
                "%d-%m-%y",  # 29-10-25 (dash separator)
                "%Y/%m/%d",  # 2025/10/29 (ISO-like)
                "%Y-%m-%d",  # 2025-10-29 (ISO format)
            ]

            # Try different time formats
            time_formats = [
                "%I:%M %p",  # 9:31 am (12-hour without seconds) - MOST COMMON
                "%H:%M:%S",  # 17:30:45 (24-hour with seconds)
                "%I:%M:%S %p",  # 5:30:45 PM (12-hour with seconds)
                "%H:%M",  # 17:30 (24-hour without seconds)
            ]

            # Try all combinations
            for date_fmt in date_formats:
                for time_fmt in time_formats:
                    try:
                        combined = f"{date_str} {time_str}"
                        dt = datetime.strptime(combined, f"{date_fmt} {time_fmt}")
                        return dt.isoformat()
                    except ValueError:
                        continue

            logger.warning(f"Failed to parse timestamp: {date_str} {time_str}")
            return None

        except Exception as e:
            logger.error(f"Error parsing timestamp: {e}")
            return None

    def _is_system_message(self, text: str) -> bool:
        """
        Check if message is a system message (should be filtered out).

        Args:
            text: Message text

        Returns:
            True if system message
        """
        system_patterns = [
            "Messages and calls are end-to-end encrypted",
            "created group",
            "added",
            "left",
            "changed the subject",
            "changed this group's icon",
            "You deleted this message",
            "This message was deleted",
            "image omitted",
            "video omitted",
            "audio omitted",
            "document omitted",
            "sticker omitted",
            "GIF omitted",
            "Contact card omitted",
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
        from uuid import uuid4

        from app.services.embedding import generate_embedding

        # Extract content
        content = message["text"]
        sender = message["sender"]

        # Generate embedding for message
        embedding = await generate_embedding(content)

        # Create title from first 50 chars
        title = f"WhatsApp Export: {sender} - {content[:50]}..."

        # Prepare document for ingestion
        document = {
            "id": str(uuid4()),
            "title": title,
            "content": content,
            "embedding": embedding,
            "source": "whatsapp_export",
            "source_id": f"export_{source_metadata.get('file_name', 'unknown')}_{message.get('timestamp', 'unknown')}",
            "source_metadata": {
                "platform": "whatsapp",
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
_parser: WhatsAppExportParser | None = None


def get_whatsapp_export_parser() -> WhatsAppExportParser:
    """Get WhatsApp export parser singleton instance."""
    global _parser
    if _parser is None:
        _parser = WhatsAppExportParser()
    return _parser
