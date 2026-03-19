"""
Chat attachments service: upload files to Supabase Storage and manage chat_attachments table.
"""

import re
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Storage path prefix for chat attachments (within configured storage bucket)
CHAT_ATTACHMENTS_PREFIX = "chat-attachments"

# Max file size: 10MB per file
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Allowed MIME types (images + common documents)
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "application/pdf",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "text/plain",
    "text/csv",
}

# Extension to MIME mapping for validation
EXT_TO_MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain",
    "csv": "text/csv",
}


def _sanitize_filename(filename: str) -> str:
    """Remove path traversal and dangerous characters from filename."""
    # Get basename only
    name = Path(filename).name
    # Replace unsafe chars
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name[:200] or "file"


def _ensure_storage_bucket_exists() -> None:
    """Create the storage bucket if it does not exist (for chat attachments)."""
    from app.db.supabase import get_supabase_client

    supabase = get_supabase_client()
    bucket_name = settings.storage_bucket
    try:
        supabase.storage.create_bucket(
            bucket_name,
            options={"public": False},  # Private bucket, use signed URLs
        )
        logger.info(f"Created storage bucket: {bucket_name}")
    except Exception as e:
        err_str = str(e).lower()
        if "already exists" in err_str or "duplicate" in err_str or "409" in str(e):
            pass  # Bucket exists, continue
        else:
            logger.warning(f"Could not ensure bucket {bucket_name} exists: {e}")


async def upload_chat_attachment(
    *,
    file_content: bytes,
    filename: str,
    mime_type: str | None,
    message_id: str,
    session_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Upload a file to Supabase Storage and create chat_attachments record.

    Returns:
        Dict with id, filename, file_type, file_size_bytes, storage_path, mime_type
    """
    from app.db.supabase import get_supabase_client

    _ensure_storage_bucket_exists()

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB")

    ext = Path(filename).suffix.lower().lstrip(".")
    inferred_mime = EXT_TO_MIME.get(ext)
    mime = mime_type or inferred_mime or "application/octet-stream"

    if mime not in ALLOWED_MIME_TYPES and inferred_mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f"File type not allowed: {ext or 'unknown'}")

    safe_filename = _sanitize_filename(filename)
    unique_id = str(uuid.uuid4())[:8]
    storage_path = f"{CHAT_ATTACHMENTS_PREFIX}/{user_id}/{session_id}/{message_id}/{unique_id}_{safe_filename}"

    supabase = get_supabase_client()
    bucket = supabase.storage.from_(settings.storage_bucket)

    # Upload bytes
    bucket.upload(
        storage_path,
        file_content,
        file_options={"content-type": mime, "upsert": "true"},
    )

    # Insert into chat_attachments
    row = {
        "message_id": message_id,
        "session_id": session_id,
        "filename": safe_filename,
        "file_type": ext or "bin",
        "file_size_bytes": len(file_content),
        "storage_path": storage_path,
        "mime_type": mime,
    }
    response = supabase.table("chat_attachments").insert(row).execute()

    if not response.data:
        raise RuntimeError("Failed to create chat_attachments record")

    record = response.data[0]
    return {
        "id": record["id"],
        "filename": record["filename"],
        "file_type": record["file_type"],
        "file_size_bytes": record["file_size_bytes"],
        "storage_path": record["storage_path"],
        "mime_type": record.get("mime_type"),
    }


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Get a signed URL for an attachment (1 hour default)."""
    from app.db.supabase import get_supabase_client

    supabase = get_supabase_client()
    bucket = supabase.storage.from_(settings.storage_bucket)
    result = bucket.create_signed_url(storage_path, expires_in)
    return result.get("signedUrl") or result.get("signedURL") or ""


async def extract_text_from_attachment(
    storage_path: str,
    filename: str,
    file_type: str,
    mime_type: str | None,
) -> str:
    """
    Download attachment from storage and extract text for LLM context.
    Supports: PDF, TXT, CSV, DOCX, DOC, XLSX. Returns empty string on failure.
    """
    from app.db.supabase import get_supabase_client
    import io

    try:
        supabase = get_supabase_client()
        bucket = supabase.storage.from_(settings.storage_bucket)
        downloaded = bucket.download(storage_path)
        if isinstance(downloaded, bytes):
            content = downloaded
        elif hasattr(downloaded, "read"):
            content = downloaded.read()
        else:
            content = bytes(downloaded) if downloaded else b""

        if not content:
            logger.warning(f"Empty content for {filename} at {storage_path}")
            return ""

        ext = (file_type or "").lower().strip()
        if ext == "pdf":
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
            return "\n\n".join(parts) if parts else ""
        if ext in ("txt", "csv", "md"):
            return content.decode("utf-8", errors="replace")
        if ext == "docx":
            from docx import Document
            doc = Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        if ext == "doc":
            import tempfile
            import asyncio
            with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                from doc2txt import extract_text
                result = await asyncio.to_thread(extract_text, tmp_path, True)
                return result or ""
            finally:
                import os
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        if ext == "xlsx":
            import pandas as pd
            df = pd.read_excel(io.BytesIO(content), sheet_name=None)
            parts = []
            for sheet_name, sheet_df in df.items():
                parts.append(f"[Sheet: {sheet_name}]\n{sheet_df.to_string()}")
            return "\n\n".join(parts) if parts else ""
        logger.info(f"No text extractor for file type: {ext} ({filename})")
        return ""
    except Exception as e:
        logger.warning(f"Could not extract text from {filename} (type={file_type}): {e}", exc_info=True)
        return ""


async def get_attachment_context_for_message(message_id: str) -> str:
    """
    Fetch all attachments for a message, extract text, and return combined context.
    Used to pass uploaded file content to the agent when user asks about "this file".
    """
    from app.db.supabase import get_supabase_client

    supabase = get_supabase_client()
    response = (
        supabase.table("chat_attachments")
        .select("storage_path, filename, file_type, mime_type")
        .eq("message_id", message_id)
        .execute()
    )
    if not response.data:
        logger.info(f"No chat_attachments found for message_id={message_id}")
        return ""

    logger.info(f"Found {len(response.data)} attachment(s) for message {message_id}: {[r['filename'] for r in response.data]}")
    parts = []
    for row in response.data:
        text = await extract_text_from_attachment(
            storage_path=row["storage_path"],
            filename=row["filename"],
            file_type=row.get("file_type", ""),
            mime_type=row.get("mime_type"),
        )
        if text.strip():
            parts.append(f"--- Content from attached file: {row['filename']} ---\n{text.strip()}")
            logger.info(f"Extracted {len(text)} chars from {row['filename']}")
        else:
            logger.warning(f"Empty extraction for {row['filename']} (type={row.get('file_type')})")
    result = "\n\n".join(parts) if parts else ""
    if not result:
        logger.warning(f"No text extracted from any attachment for message {message_id}")
    return result


async def get_attachments_for_messages(
    message_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch attachments for a list of message IDs and return signed URLs.
    Returns: {message_id: [{id, filename, file_type, file_size_bytes, url, mime_type}, ...]}
    """
    if not message_ids:
        return {}

    from app.db.supabase import get_supabase_client

    supabase = get_supabase_client()
    response = (
        supabase.table("chat_attachments")
        .select("id, message_id, filename, file_type, file_size_bytes, storage_path, mime_type")
        .in_("message_id", message_ids)
        .execute()
    )

    result: dict[str, list[dict[str, Any]]] = {mid: [] for mid in message_ids}
    for row in response.data or []:
        mid = row["message_id"]
        storage_path = row["storage_path"]
        try:
            url = get_signed_url(storage_path)
        except Exception as e:
            logger.warning(f"Failed to create signed URL for {storage_path}: {e}")
            url = ""
        result[mid].append({
            "id": row["id"],
            "filename": row["filename"],
            "file_type": row["file_type"],
            "file_size_bytes": row["file_size_bytes"],
            "url": url,
            "mime_type": row.get("mime_type"),
        })
    return result
