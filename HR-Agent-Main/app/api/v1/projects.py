"""
Projects API endpoints for project-based chats (Gemini-style).
"""

from typing import Optional
from uuid import UUID
from pathlib import Path
import tempfile
import aiofiles

from fastapi import APIRouter, HTTPException, Query, Depends, File, UploadFile, Form, status
from app.models.projects import (
    ProjectCreate,
    ProjectUpdate,
    ProjectSummary,
    ProjectDetail,
    ProjectsListResponse,
)
from app.models.chat import SessionSummary, SessionsListResponse
from app.models.documents import DocumentListItem, DocumentListResponse, DocumentUploadResponse
from app.services.chat import get_sessions_list
from app.services.ingestion import get_ingestion_service
from app.db.supabase import get_supabase_client
from app.core.config import settings
from app.core.logging import get_logger
from app.core.dependencies import get_current_user_id

logger = get_logger(__name__)
router = APIRouter()


def _ensure_project_ownership(project_id: str, user_id: str) -> dict:
    """Verify user owns project and return project row. Raises HTTPException if not."""
    from postgrest.exceptions import APIError

    db = get_supabase_client()
    try:
        result = (
            db.table("projects")
            .select("*")
            .eq("id", project_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except APIError as e:
        raise HTTPException(status_code=404, detail="Project not found or access denied") from e
    # maybe_single() returns None when 0 rows, or a response with .data when 1 row
    if result is None or not getattr(result, "data", None):
        raise HTTPException(status_code=404, detail="Project not found or access denied")
    return result.data


@router.get("/", response_model=ProjectsListResponse)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user_id: str = Depends(get_current_user_id),
) -> ProjectsListResponse:
    """List user's projects, sorted by most recently updated."""
    import math

    db = get_supabase_client()
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    query = (
        db.table("projects")
        .select("*", count="exact")
        .eq("user_id", current_user_id)
        .order("updated_at", desc=True)
        .range(offset, offset + page_size - 1)
    )
    result = query.execute()

    total = result.count if result.count is not None else len(result.data or [])
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    projects = [
        ProjectSummary(
            id=p["id"],
            user_id=p["user_id"],
            name=p["name"],
            description=p.get("description"),
            created_at=p["created_at"],
            updated_at=p["updated_at"],
        )
        for p in (result.data or [])
    ]

    return ProjectsListResponse(
        projects=projects,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user_id: str = Depends(get_current_user_id),
) -> ProjectDetail:
    """Create a new project."""
    db = get_supabase_client()
    data = {
        "user_id": current_user_id,
        "name": body.name,
        "description": body.description,
    }
    result = db.table("projects").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create project")
    p = result.data[0]
    return ProjectDetail(
        id=p["id"],
        user_id=p["user_id"],
        name=p["name"],
        description=p.get("description"),
        created_at=p["created_at"],
        updated_at=p["updated_at"],
    )


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
) -> ProjectDetail:
    """Get project details."""
    p = _ensure_project_ownership(str(project_id), current_user_id)
    return ProjectDetail(
        id=p["id"],
        user_id=p["user_id"],
        name=p["name"],
        description=p.get("description"),
        created_at=p["created_at"],
        updated_at=p["updated_at"],
    )


@router.patch("/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    current_user_id: str = Depends(get_current_user_id),
) -> ProjectDetail:
    """Update project."""
    _ensure_project_ownership(str(project_id), current_user_id)
    db = get_supabase_client()
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        # Return current state
        p = _ensure_project_ownership(str(project_id), current_user_id)
        return ProjectDetail(
            id=p["id"],
            user_id=p["user_id"],
            name=p["name"],
            description=p.get("description"),
            created_at=p["created_at"],
            updated_at=p["updated_at"],
        )
    result = db.table("projects").update(update_data).eq("id", str(project_id)).eq("user_id", current_user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    p = result.data[0]
    return ProjectDetail(
        id=p["id"],
        user_id=p["user_id"],
        name=p["name"],
        description=p.get("description"),
        created_at=p["created_at"],
        updated_at=p["updated_at"],
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """Delete project. Project documents are cascade-deleted. Chat sessions have project_id set to NULL."""
    _ensure_project_ownership(str(project_id), current_user_id)
    db = get_supabase_client()
    db.table("projects").delete().eq("id", str(project_id)).eq("user_id", current_user_id).execute()
    return {"success": True, "message": "Project deleted"}


@router.get("/{project_id}/documents", response_model=DocumentListResponse)
async def list_project_documents(
    project_id: UUID,
    search: Optional[str] = Query(None, description="Search by filename, title"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
) -> DocumentListResponse:
    """List documents belonging to the project."""
    _ensure_project_ownership(str(project_id), current_user_id)
    db = get_supabase_client()

    query = db.table("documents").select("*", count="exact").eq("project_id", str(project_id))

    if search and (term := search.replace("*", "").replace("%", "").strip()):
        pattern = f"*{term}*"
        query = query.or_(f"title.ilike.{pattern},original_filename.ilike.{pattern},filename.ilike.{pattern}")

    offset = (page - 1) * page_size
    result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

    total = result.count if result.count is not None else len(result.data or [])
    total_pages = max(1, (total + page_size - 1) // page_size)

    documents = [
        DocumentListItem(
            id=doc["id"],
            title=doc.get("original_filename", doc.get("filename", doc.get("title", "Untitled"))),
            source=doc.get("source", "document"),
            processing_status=doc.get("processing_status", "unknown"),
            created_at=doc["created_at"],
            province=doc.get("province"),
            original_filename=doc.get("original_filename", doc.get("filename")),
            metadata=doc.get("metadata", {}),
        )
        for doc in (result.data or [])
    ]

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/{project_id}/documents/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_project_document(
    project_id: UUID,
    file: UploadFile = File(..., description="Document file"),
    title: Optional[str] = Form(None),
    province: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    current_user_id: str = Depends(get_current_user_id),
) -> DocumentUploadResponse:
    """Upload a document to the project."""
    _ensure_project_ownership(str(project_id), current_user_id)

    file_ext = Path(file.filename).suffix.lower().lstrip(".")
    if file_ext not in settings.docling_supported_formats_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported: {', '.join(settings.docling_supported_formats_list)}",
        )

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum ({settings.max_upload_size_mb}MB)",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
        temp_path = Path(temp_file.name)
        async with aiofiles.open(temp_path, "wb") as f:
            content = await file.read()
            await f.write(content)

    try:
        ingestion_service = get_ingestion_service()
        doc_metadata = {}
        if metadata:
            import json
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                pass

        result = await ingestion_service.ingest_document(
            file_path=temp_path,
            title=title or file.filename,
            original_filename=file.filename,
            source="project_upload",
            province=province,
            metadata=doc_metadata,
            project_id=str(project_id),
        )

        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Document processing failed"),
            )

        return DocumentUploadResponse(
            document_id=result["document_id"],
            status="completed",
            message=f"Document uploaded: {result['chunks_created']} chunks created",
        )
    finally:
        try:
            temp_path.unlink()
        except Exception:
            pass


@router.get("/{project_id}/sessions", response_model=SessionsListResponse)
async def list_project_sessions(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
) -> SessionsListResponse:
    """List chat sessions in the project."""
    _ensure_project_ownership(str(project_id), current_user_id)
    return await get_sessions_list(
        page=page,
        page_size=page_size,
        user_id=current_user_id,
        project_id=str(project_id),
    )
