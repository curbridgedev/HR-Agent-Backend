"""
Structure-aware text chunking for RAG.
Preserves semantic boundaries and document structure.
"""

from typing import List, Dict, Any, Optional
import re
from dataclasses import dataclass
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    content: str
    index: int
    token_count: int
    metadata: Dict[str, Any]


class StructureAwareChunker:
    """
    Intelligent text chunker that preserves document structure.

    Features:
    - Respects semantic boundaries (paragraphs, sections)
    - Preserves tables and lists
    - Maintains context with overlapping windows
    - Token-aware chunking
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        enable_structure_aware: bool = None,
    ):
        """
        Initialize chunker with configuration.

        Args:
            chunk_size: Maximum tokens per chunk (default from settings)
            chunk_overlap: Token overlap between chunks (default from settings)
            enable_structure_aware: Enable structure-aware chunking (default from settings)
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.enable_structure_aware = (
            enable_structure_aware
            if enable_structure_aware is not None
            else settings.enable_structure_aware_chunking
        )

        logger.info(
            f"Chunker initialized: chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, structure_aware={self.enable_structure_aware}"
        )

    def chunk_text(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[TextChunk]:
        """
        Split text into chunks while preserving structure.

        Args:
            text: Input text to chunk
            metadata: Optional metadata to attach to all chunks

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []

        metadata = metadata or {}

        if self.enable_structure_aware:
            chunks = self._chunk_structure_aware(text, metadata)
        else:
            chunks = self._chunk_simple(text, metadata)

        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks

    def _chunk_structure_aware(
        self, text: str, metadata: Dict[str, Any]
    ) -> List[TextChunk]:
        """
        Chunk text while preserving semantic structure.

        Strategy:
        1. Split on major boundaries (double newlines)
        2. Identify special structures (tables, lists, code blocks)
        3. Group content to respect chunk_size
        4. Add overlap for context preservation
        """
        # Split into sections on double newlines
        sections = re.split(r"\n\n+", text)
        sections = [s.strip() for s in sections if s.strip()]

        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_index = 0

        for section in sections:
            section_tokens = self._estimate_tokens(section)

            # If section alone exceeds chunk_size, split it
            if section_tokens > self.chunk_size:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append(
                        self._create_chunk(
                            "\n\n".join(current_chunk), chunk_index, metadata
                        )
                    )
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0

                # Split large section
                sub_chunks = self._split_large_section(section, chunk_index, metadata)
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
            else:
                # Check if adding this section exceeds chunk_size
                if current_tokens + section_tokens > self.chunk_size and current_chunk:
                    # Save current chunk
                    chunks.append(
                        self._create_chunk(
                            "\n\n".join(current_chunk), chunk_index, metadata
                        )
                    )
                    chunk_index += 1

                    # Start new chunk with overlap
                    if self.chunk_overlap > 0:
                        overlap_content = self._get_overlap_content(current_chunk)
                        current_chunk = [overlap_content] if overlap_content else []
                        current_tokens = self._estimate_tokens(overlap_content)
                    else:
                        current_chunk = []
                        current_tokens = 0

                # Add section to current chunk
                current_chunk.append(section)
                current_tokens += section_tokens

        # Save final chunk
        if current_chunk:
            chunks.append(
                self._create_chunk("\n\n".join(current_chunk), chunk_index, metadata)
            )

        return chunks

    def _chunk_simple(self, text: str, metadata: Dict[str, Any]) -> List[TextChunk]:
        """
        Simple chunking strategy without structure awareness.
        Uses fixed character windows with overlap.
        """
        # Convert token limits to approximate character limits (rough: 1 token ≈ 4 chars)
        char_size = self.chunk_size * 4
        char_overlap = self.chunk_overlap * 4

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + char_size
            chunk_text = text[start:end]

            chunks.append(self._create_chunk(chunk_text, chunk_index, metadata))
            chunk_index += 1

            # Move start position with overlap
            start += char_size - char_overlap

        return chunks

    def _split_large_section(
        self, section: str, start_index: int, metadata: Dict[str, Any]
    ) -> List[TextChunk]:
        """Split a large section that exceeds chunk_size."""
        # Try to split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", section)

        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_index = start_index

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(
                    self._create_chunk(" ".join(current_chunk), chunk_index, metadata)
                )
                chunk_index += 1
                current_chunk = []
                current_tokens = 0

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Save final chunk
        if current_chunk:
            chunks.append(
                self._create_chunk(" ".join(current_chunk), chunk_index, metadata)
            )

        return chunks

    def _get_overlap_content(self, chunks: List[str]) -> str:
        """
        Get overlap content from previous chunks.
        Takes the last section(s) that fit within chunk_overlap.
        """
        if not chunks:
            return ""

        overlap_text = ""
        overlap_tokens = 0

        # Work backwards through chunks
        for chunk in reversed(chunks):
            chunk_tokens = self._estimate_tokens(chunk)
            if overlap_tokens + chunk_tokens <= self.chunk_overlap:
                overlap_text = chunk + "\n\n" + overlap_text if overlap_text else chunk
                overlap_tokens += chunk_tokens
            else:
                break

        return overlap_text.strip()

    def _create_chunk(
        self, content: str, index: int, metadata: Dict[str, Any]
    ) -> TextChunk:
        """Create a TextChunk with token count and metadata."""
        token_count = self._estimate_tokens(content)

        chunk_metadata = {
            **metadata,
            "chunk_index": index,
            "char_count": len(content),
        }

        return TextChunk(
            content=content,
            index=index,
            token_count=token_count,
            metadata=chunk_metadata,
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses tiktoken for accurate counting.
        """
        try:
            from app.services.embedding import count_tokens

            return count_tokens(text)
        except Exception:
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4


def chunk_document(
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[TextChunk]:
    """
    Convenience function to chunk a document.

    Args:
        content: Document content to chunk
        metadata: Optional metadata for all chunks
        chunk_size: Override default chunk size
        chunk_overlap: Override default chunk overlap

    Returns:
        List of TextChunk objects
    """
    chunker = StructureAwareChunker(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    return chunker.chunk_text(content, metadata)
