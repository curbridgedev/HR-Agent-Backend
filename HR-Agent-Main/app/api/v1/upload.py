"""
File upload endpoints for manual data ingestion.

Handles WhatsApp/Telegram/Slack chat export uploads for historical data ingestion.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.models.upload import UploadResponse
from app.services.chat_export_parser import get_whatsapp_export_parser
from app.services.telegram_export_parser import get_telegram_export_parser

logger = get_logger(__name__)
router = APIRouter()


@router.post("/whatsapp-export", response_model=UploadResponse)
async def upload_whatsapp_export(
    file: UploadFile = File(..., description="WhatsApp chat export file (.txt)"),
) -> UploadResponse:
    """
    Upload and ingest WhatsApp chat export file.

    WhatsApp chat exports can be obtained by:
    1. Open the chat in WhatsApp
    2. Tap the three dots menu → More → Export chat
    3. Choose "Without Media"
    4. Save the .txt file
    5. Upload here

    The file will be parsed and all messages will be ingested into the knowledge base.

    **Note**: This is for historical data only. Real-time messages are captured via webhook.
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required",
            )

        if not file.filename.endswith(".txt"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .txt files are supported for WhatsApp exports",
            )

        # Check file size
        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
        file_size = 0

        # Read file content
        content_bytes = await file.read()
        file_size = len(content_bytes)

        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum of {settings.max_upload_size_mb}MB",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        # Decode content
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                content = content_bytes.decode("utf-8-sig")  # UTF-8 with BOM
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode("latin-1")
                except UnicodeDecodeError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Unable to decode file. Please ensure it's a valid text file.",
                    ) from e

        logger.info(f"Processing WhatsApp export upload: {file.filename} ({file_size} bytes)")

        # Parse and ingest
        parser = get_whatsapp_export_parser()
        result = await parser.parse_and_ingest(
            file_content=content,
            source_metadata={
                "file_name": file.filename,
                "file_size_bytes": file_size,
                "uploaded_by": "admin",  # TODO: Add authentication and get user
            },
        )

        logger.info(
            f"WhatsApp export ingestion complete: {result['messages_ingested']} messages ingested"
        )

        return UploadResponse(
            status=result["status"],
            message=result["message"],
            file_name=file.filename,
            messages_ingested=result["messages_ingested"],
            messages_failed=result["messages_failed"],
            errors=result.get("errors"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing WhatsApp export upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}",
        ) from e


@router.post("/telegram-export", response_model=UploadResponse)
async def upload_telegram_export(
    file: UploadFile = File(..., description="Telegram chat export file (.txt)"),
) -> UploadResponse:
    """
    Upload and ingest Telegram chat export file.

    Telegram chat exports can be obtained by:
    1. Open Telegram Desktop
    2. Go to the chat you want to export
    3. Click the three dots menu → Export chat history
    4. Choose format: "Machine-readable JSON" or "Human-readable text"
    5. Uncheck "Photos", "Videos", etc. (only export text)
    6. Click "Export"
    7. Upload the resulting .txt file here

    The file will be parsed and all messages will be ingested into the knowledge base.

    **Note**: This is for historical data only. Real-time messages are captured via Telethon.
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required",
            )

        if not file.filename.endswith(".txt"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .txt files are supported for Telegram exports",
            )

        # Check file size
        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024

        # Read file content
        content_bytes = await file.read()
        file_size = len(content_bytes)

        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum of {settings.max_upload_size_mb}MB",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        # Decode content (Telegram exports are usually UTF-8)
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode("utf-8-sig")  # UTF-8 with BOM
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode("latin-1")
                except UnicodeDecodeError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Unable to decode file. Please ensure it's a valid text file.",
                    ) from e

        logger.info(f"Processing Telegram export upload: {file.filename} ({file_size} bytes)")

        # Parse and ingest
        parser = get_telegram_export_parser()
        result = await parser.parse_and_ingest(
            file_content=content,
            source_metadata={
                "file_name": file.filename,
                "file_size_bytes": file_size,
                "uploaded_by": "admin",  # TODO: Add authentication and get user
            },
        )

        logger.info(
            f"Telegram export ingestion complete: {result['messages_ingested']} messages ingested"
        )

        return UploadResponse(
            status=result["status"],
            message=result["message"],
            file_name=file.filename,
            messages_ingested=result["messages_ingested"],
            messages_failed=result["messages_failed"],
            errors=result.get("errors"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Telegram export upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}",
        ) from e


@router.post("/slack-export", response_model=UploadResponse)
async def upload_slack_export(
    file: UploadFile = File(..., description="Slack export archive (.zip)"),
) -> JSONResponse:
    """
    Upload and ingest Slack export archive.

    **Coming soon**: Slack export ingestion is not yet implemented.
    """
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "status": "not_implemented",
            "message": "Slack export ingestion coming soon",
        },
    )
