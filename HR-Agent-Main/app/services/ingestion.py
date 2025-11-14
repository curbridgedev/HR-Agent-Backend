"""
Document ingestion service.
Orchestrates document processing, chunking, embedding, and storage.
"""

from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.pii import AnonymizationStrategy
from app.services.embedding import generate_embeddings_batch
from app.services.pii import anonymize_text
from app.utils.chunking import StructureAwareChunker
from app.utils.docling import DoclingProcessor

logger = get_logger(__name__)


class DocumentIngestionService:
    """
    Orchestrates the complete document ingestion pipeline.

    Pipeline:
    1. Process document (extract text, preserve structure)
    2. Chunk content (structure-aware)
    3. Generate embeddings (batch processing)
    4. Store in vector database
    """

    def __init__(self) -> None:
        """Initialize ingestion service with processors."""
        self.doc_processor = DoclingProcessor()
        self.chunker = StructureAwareChunker()
        self.db = get_supabase_client()

    async def ingest_document(
        self,
        file_path: Path,
        title: str | None = None,
        source: str = "admin_upload",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ingest a document through the complete pipeline.

        Args:
            file_path: Path to the document file
            title: Document title (auto-generated from filename if not provided)
            source: Source of the document
            metadata: Additional metadata

        Returns:
            Dictionary with ingestion results:
            {
                "document_id": str,
                "title": str,
                "chunks_created": int,
                "tokens_processed": int,
                "status": str,
            }
        """
        document_id = str(uuid4())
        title = title or file_path.stem
        metadata = metadata or {}

        try:
            logger.info(f"Starting ingestion for {file_path.name}")

            # Step 1: Process document
            logger.info(f"[{document_id}] Processing document with Docling...")
            doc_result = await self.doc_processor.process_file(file_path)
            content = doc_result["content"]
            doc_metadata = doc_result["metadata"]

            # Merge metadata
            combined_metadata = {**metadata, **doc_metadata}

            logger.info(
                f"[{document_id}] Extracted {len(content)} characters "
                f"({doc_metadata.get('page_count', 0)} pages)"
            )

            # Step 2: Chunk content
            logger.info(f"[{document_id}] Chunking content...")
            chunks = self.chunker.chunk_text(content, combined_metadata)
            logger.info(f"[{document_id}] Created {len(chunks)} chunks")

            # Step 2.5: Anonymize PII in chunks if enabled
            pii_anonymization_results = []
            if settings.pii_anonymization_enabled:
                logger.info(f"[{document_id}] Anonymizing PII in {len(chunks)} chunks...")
                total_pii_found = 0

                for chunk in chunks:
                    anonymization_result = await anonymize_text(
                        text=chunk.content,
                        strategy=AnonymizationStrategy(settings.pii_default_strategy),
                        placeholder=settings.pii_redaction_placeholder,
                        min_score=settings.pii_min_confidence_score,
                    )

                    # Update chunk content with anonymized text
                    chunk.content = anonymization_result.anonymized_text

                    # Track PII found
                    if anonymization_result.anonymization_applied:
                        total_pii_found += len(anonymization_result.entities_found)

                    # Store anonymization metadata for this chunk
                    pii_anonymization_results.append({
                        "chunk_index": chunk.index,
                        "anonymization_applied": anonymization_result.anonymization_applied,
                        "entities_found": [
                            {
                                "type": entity.entity_type.value,
                                "score": entity.score,
                            }
                            for entity in anonymization_result.entities_found
                        ],
                    })

                if total_pii_found > 0:
                    logger.info(
                        f"[{document_id}] Anonymized {total_pii_found} PII entities across {len(chunks)} chunks"
                    )

            # Step 3: Generate embeddings (on anonymized content)
            logger.info(f"[{document_id}] Generating embeddings...")
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await generate_embeddings_batch(chunk_texts)
            logger.info(f"[{document_id}] Generated {len(embeddings)} embeddings")

            # Step 4: Store in database
            logger.info(f"[{document_id}] Storing in database...")
            total_tokens = sum(chunk.token_count for chunk in chunks)

            # First, create document metadata record
            doc_record = {
                "id": document_id,
                "filename": file_path.name,
                "original_filename": file_path.name,
                "file_type": file_path.suffix.lstrip('.') or 'unknown',
                "file_size_bytes": file_path.stat().st_size if file_path.exists() else 0,
                "storage_path": str(file_path),
                "processing_status": "completed",
                "chunk_count": len(chunks),
                "total_tokens": total_tokens,
                "metadata": combined_metadata,
            }

            try:
                self.db.table("documents").insert(doc_record).execute()
                logger.info(f"[{document_id}] Document metadata record created")
            except Exception as doc_error:
                logger.warning(f"[{document_id}] Failed to create document record: {doc_error}")
                # Continue anyway - chunks are more important

            # Store each chunk in knowledge_base
            stored_count = 0
            for chunk, embedding in zip(chunks, embeddings):
                # Get PII metadata for this chunk
                pii_metadata = {}
                if settings.pii_anonymization_enabled and pii_anonymization_results:
                    chunk_pii_result = pii_anonymization_results[chunk.index]
                    pii_metadata = {
                        "pii_anonymization_applied": chunk_pii_result["anonymization_applied"],
                        "pii_entities_found": chunk_pii_result["entities_found"],
                    }

                # Combine all metadata including source info
                chunk_metadata = {
                    **chunk.metadata,
                    **pii_metadata,
                    "original_file": file_path.name,
                    "chunk_index": chunk.index,
                    "total_chunks": len(chunks),
                    "parent_document_id": document_id,
                }

                # Map source to valid source_type values
                source_type_map = {
                    "admin_upload": "document",
                    "api_upload": "document",
                    "manual": "manual",
                    "slack": "slack",
                    "whatsapp": "whatsapp",
                    "telegram": "telegram",
                }
                source_type = source_type_map.get(source, "document")

                chunk_doc = {
                    "title": f"{title} (chunk {chunk.index + 1}/{len(chunks)})",
                    "content": chunk.content,
                    "embedding": embedding,
                    "source_type": source_type,
                    "source_id": document_id,  # Link all chunks to same document
                    "document_id": document_id,  # FK to documents table
                    "chunk_index": chunk.index,
                    "tokens": chunk.token_count,
                    "metadata": chunk_metadata,
                }

                result = self.db.table("knowledge_base").insert(chunk_doc).execute()

                if result.data:
                    stored_count += 1

            logger.info(
                f"[{document_id}] Ingestion complete: "
                f"{stored_count} chunks stored, {total_tokens} tokens processed"
            )

            return {
                "document_id": document_id,
                "title": title,
                "chunks_created": stored_count,
                "tokens_processed": total_tokens,
                "status": "completed",
                "message": f"Document ingested successfully: {stored_count} chunks created",
            }

        except Exception as e:
            logger.error(f"[{document_id}] Ingestion failed: {e}", exc_info=True)

            # Store failed document record in documents table
            try:
                error_doc_record = {
                    "id": document_id,
                    "filename": file_path.name if file_path.exists() else title,
                    "original_filename": file_path.name if file_path.exists() else title,
                    "file_type": file_path.suffix.lstrip('.') if file_path.exists() else 'unknown',
                    "file_size_bytes": file_path.stat().st_size if file_path.exists() else 0,
                    "storage_path": str(file_path) if file_path.exists() else "",
                    "processing_status": "failed",
                    "processing_error": str(e),
                    "metadata": metadata or {},
                }
                self.db.table("documents").insert(error_doc_record).execute()
            except Exception as store_error:
                logger.error(f"Failed to store error document: {store_error}")

            return {
                "document_id": document_id,
                "title": title,
                "chunks_created": 0,
                "tokens_processed": 0,
                "status": "failed",
                "error": str(e),
            }

    async def ingest_multiple(
        self,
        file_paths: list[Path],
        source: str = "admin_upload",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ingest multiple documents.

        Args:
            file_paths: List of file paths to ingest
            source: Source for all documents
            metadata: Shared metadata for all documents

        Returns:
            Dictionary with batch ingestion results
        """
        logger.info(f"Starting batch ingestion of {len(file_paths)} documents")

        results = []
        success_count = 0
        failed_count = 0

        for file_path in file_paths:
            try:
                result = await self.ingest_document(file_path, source=source, metadata=metadata)

                if result["status"] == "completed":
                    success_count += 1
                else:
                    failed_count += 1

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {e}")
                failed_count += 1
                results.append({
                    "document_id": str(uuid4()),
                    "title": file_path.stem,
                    "status": "failed",
                    "error": str(e),
                })

        logger.info(
            f"Batch ingestion complete: "
            f"{success_count} succeeded, {failed_count} failed"
        )

        return {
            "total": len(file_paths),
            "succeeded": success_count,
            "failed": failed_count,
            "results": results,
        }

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and all its chunks.

        Args:
            document_id: Document ID (primary key in documents table)

        Returns:
            True if deletion successful
        """
        try:
            # First, check if document exists in documents table
            check_result = self.db.table("documents").select("id").eq("id", document_id).execute()

            if not check_result.data:
                logger.warning(f"Document not found: {document_id}")
                return False

            # Delete all chunks from knowledge_base
            chunks_result = self.db.table("knowledge_base").delete().eq("document_id", document_id).execute()
            chunk_count = len(chunks_result.data) if chunks_result.data else 0
            logger.info(f"Deleted {chunk_count} chunks for document {document_id}")

            # Delete the document record from documents table
            doc_result = self.db.table("documents").delete().eq("id", document_id).execute()
            deleted_count = len(doc_result.data) if doc_result.data else 0

            if deleted_count > 0:
                logger.info(f"Deleted document {document_id}")
                return True
            else:
                logger.warning(f"Document {document_id} not deleted")
                return False

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    async def get_document_status(self, document_id: str) -> dict[str, Any] | None:
        """
        Get processing status of a document.

        Args:
            document_id: Document ID (primary key)

        Returns:
            Document status information or None if not found
        """
        try:
            # Get the document metadata from documents table
            doc_result = self.db.table("documents").select("*").eq("id", document_id).execute()

            if not doc_result.data:
                logger.warning(f"Document not found: {document_id}")
                return None

            doc = doc_result.data[0]

            # Get chunk count from knowledge_base
            chunks_result = self.db.table("knowledge_base").select("id").eq("document_id", document_id).execute()
            chunk_count = len(chunks_result.data) if chunks_result.data else 0

            return {
                "document_id": document_id,
                "title": doc.get("filename", "Untitled"),
                "total_chunks": doc.get("chunk_count", chunk_count),
                "completed_chunks": chunk_count if doc.get("processing_status") == "completed" else 0,
                "failed_chunks": 0 if doc.get("processing_status") == "completed" else doc.get("chunk_count", 0),
                "status": doc.get("processing_status", "unknown"),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "processing_error": doc.get("processing_error"),
            }

        except Exception as e:
            logger.error(f"Failed to get document status {document_id}: {e}")
            return None


# Global service instance
_ingestion_service = None


def get_ingestion_service() -> DocumentIngestionService:
    """Get or create global ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = DocumentIngestionService()
    return _ingestion_service
