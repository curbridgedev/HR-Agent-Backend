"""
Document upload and management API endpoints.
"""

from typing import List, Optional
from pathlib import Path
from uuid import UUID
import tempfile
import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, status
from fastapi.responses import JSONResponse
from app.models.documents import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentListItem,
    DocumentDetail,
    DocumentDeleteResponse,
)
from app.services.ingestion import get_ingestion_service
from app.db.supabase import get_supabase_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload"),
    title: Optional[str] = Form(None, description="Document title (optional)"),
    source: str = Form("admin_upload", description="Source of document"),
    province: Optional[str] = Form(None, description="Canadian province (MB, ON, SK, AB, BC, or ALL for federal/multi-province)"),
    metadata: Optional[str] = Form(None, description="Additional metadata as JSON string"),
):
    """
    Upload and process a document.

    Supports: PDF, DOCX, XLSX, PPTX, TXT, MD

    The document will be:
    1. Validated (size, type)
    2. Processed (text extraction with structure preservation)
    3. Chunked (structure-aware chunking)
    4. Embedded (batch embedding generation)
    5. Stored (in vector database)

    Returns immediately with document ID. Processing happens in background.
    """
    try:
        # Validate file type
        file_ext = Path(file.filename).suffix.lower().lstrip(".")
        if file_ext not in settings.docling_supported_formats_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. "
                       f"Supported formats: {', '.join(settings.docling_supported_formats_list)}",
            )

        # Validate file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum ({settings.max_upload_size_mb}MB)",
            )

        logger.info(f"Uploading document: {file.filename} ({file_size / 1024 / 1024:.2f}MB)")

        # Save file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
            temp_path = Path(temp_file.name)

            # Write uploaded file
            async with aiofiles.open(temp_path, "wb") as f:
                content = await file.read()
                await f.write(content)

        try:
            # Process document
            ingestion_service = get_ingestion_service()

            # Parse metadata if provided
            doc_metadata = {}
            if metadata:
                import json
                try:
                    doc_metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid metadata JSON: {metadata}")

            result = await ingestion_service.ingest_document(
                file_path=temp_path,
                title=title or file.filename,  # Use original filename if no title provided
                source=source,
                province=province,  # Pass province for filtering
                metadata=doc_metadata,
            )

            if result["status"] == "failed":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Document processing failed: {result.get('error', 'Unknown error')}",
                )

            return DocumentUploadResponse(
                document_id=result["document_id"],
                title=result["title"],
                filename=file.filename,
                file_size=file_size,
                file_type=file.content_type or f"application/{file_ext}",
                status="completed",
                message=f"Document uploaded and processed: {result['chunks_created']} chunks created",
            )

        finally:
            # Cleanup temporary file
            try:
                temp_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_path}: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.post("/upload/bulk", status_code=status.HTTP_201_CREATED)
async def upload_documents_bulk(
    files: List[UploadFile] = File(..., description="Multiple document files"),
    source: str = Form("admin_upload", description="Source for all documents"),
    province: Optional[str] = Form(None, description="Canadian province for all documents (MB, ON, SK, AB, BC, or ALL)"),
):
    """
    Upload multiple documents at once.

    Each document is processed independently. Returns summary of successes and failures.
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per bulk upload",
        )

    results = {
        "total": len(files),
        "succeeded": 0,
        "failed": 0,
        "results": [],
    }

    ingestion_service = get_ingestion_service()

    for file in files:
        try:
            # Validate and process each file
            file_ext = Path(file.filename).suffix.lower().lstrip(".")

            if file_ext not in settings.docling_supported_formats_list:
                results["failed"] += 1
                results["results"].append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": f"Unsupported file type: {file_ext}",
                })
                continue

            # Save temporarily and process
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                temp_path = Path(temp_file.name)
                async with aiofiles.open(temp_path, "wb") as f:
                    content = await file.read()
                    await f.write(content)

            try:
                logger.info(f"Starting ingestion for {file.filename} (size: {temp_path.stat().st_size if temp_path.exists() else 0} bytes)")
                result = await ingestion_service.ingest_document(
                    file_path=temp_path,
                    title=file.filename,  # Use original filename as title
                    source=source,
                    province=province,  # Pass province for filtering
                )
                logger.info(f"Completed ingestion for {file.filename}: {result.get('status', 'unknown')}")

                if result["status"] == "completed":
                    results["succeeded"] += 1
                    results["results"].append({
                        "filename": file.filename,
                        "document_id": result["document_id"],
                        "status": "completed",
                        "chunks_created": result["chunks_created"],
                    })
                else:
                    results["failed"] += 1
                    results["results"].append({
                        "filename": file.filename,
                        "status": "failed",
                        "error": result.get("error", "Unknown error"),
                    })

            finally:
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}")
            results["failed"] += 1
            results["results"].append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e),
            })

    return results


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    source: Optional[str] = Query(None, description="Filter by source"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all documents with pagination and filtering.
    """
    try:
        db = get_supabase_client()

        # Build query
        query = db.table("documents").select("*", count="exact")

        # Apply filters
        if source:
            query = query.eq("source", source)
        if status:
            query = query.eq("processing_status", status)

        # Get total count
        count_result = query.execute()
        total = len(count_result.data) if count_result.data else 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)

        result = query.execute()

        documents = [
            DocumentListItem(
                id=doc["id"],
                title=doc.get("filename", doc.get("original_filename", "Untitled")),
                source="document",  # documents table doesn't have source field
                processing_status=doc.get("processing_status", "unknown"),
                created_at=doc["created_at"],
                metadata=doc.get("metadata", {}),
            )
            for doc in (result.data or [])
        ]

        total_pages = (total + page_size - 1) // page_size

        return DocumentListResponse(
            documents=documents,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve documents: {str(e)}",
        )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: UUID):
    """
    Get detailed information about a specific document.
    """
    try:
        db = get_supabase_client()

        # Get document by ID
        result = db.table("documents").select("*").eq("id", str(document_id)).single().execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}",
            )

        doc = result.data

        # Get first chunk from knowledge_base to show content preview
        chunk_result = supabase.table("knowledge_base").select("content").eq("document_id", document_id).limit(1).execute()
        content_preview = chunk_result.data[0]["content"] if chunk_result.data else ""

        return DocumentDetail(
            id=doc["id"],
            title=doc.get("filename", doc.get("original_filename", "Untitled")),
            content=content_preview,  # Show first chunk content as preview
            source="document",  # documents table doesn't have source field
            source_id=doc["id"],
            source_metadata={
                "filename": doc.get("filename"),
                "file_type": doc.get("file_type"),
                "file_size_bytes": doc.get("file_size_bytes"),
                "storage_path": doc.get("storage_path"),
            },
            processing_status=doc.get("processing_status", "unknown"),
            error_message=doc.get("processing_error"),  # Map to correct column name
            metadata=doc.get("metadata", {}),
            created_at=doc["created_at"],
            updated_at=doc.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document: {str(e)}",
        )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: UUID):
    """
    Delete a document and all its chunks.
    """
    try:
        ingestion_service = get_ingestion_service()
        success = await ingestion_service.delete_document(str(document_id))

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found or deletion failed: {document_id}",
            )

        return DocumentDeleteResponse(
            document_id=str(document_id),
            message="Document and all chunks deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deletion failed: {str(e)}",
        )
