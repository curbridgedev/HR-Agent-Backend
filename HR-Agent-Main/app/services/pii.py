"""
PII (Personally Identifiable Information) detection and anonymization service.

This service uses Microsoft Presidio to detect and anonymize PII in text data.
Supports multiple anonymization strategies: redact, replace, mask, hash.

Key features:
- Built-in detection for common PII types (email, phone, credit card, SSN, etc.)
- Custom pattern support for domain-specific PII
- Configurable anonymization strategies per entity type
- Audit logging for compliance
- Batch processing support
"""

from datetime import datetime
from typing import Any

from presidio_analyzer import AnalyzerEngine, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from app.core.config import settings
from app.core.logging import get_logger
from app.models.pii import (
    AnonymizationResult,
    AnonymizationStrategy,
    PIIDetectionResult,
    PIIEntityType,
    PIIPattern,
)

logger = get_logger(__name__)

# Global instances (initialized once)
_analyzer: AnalyzerEngine | None = None
_anonymizer: AnonymizerEngine | None = None
_custom_recognizers: dict[str, PatternRecognizer] = {}


def _get_analyzer() -> AnalyzerEngine:
    """Get or create Presidio AnalyzerEngine instance."""
    global _analyzer
    if _analyzer is None:
        logger.info("Initializing Presidio AnalyzerEngine with en_core_web_sm")

        # Configure NLP engine to use smaller spaCy model
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()

        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine)

        # Add custom recognizers
        for recognizer in _custom_recognizers.values():
            _analyzer.registry.add_recognizer(recognizer)

        logger.info(
            f"AnalyzerEngine initialized with {len(_custom_recognizers)} custom recognizers"
        )

    return _analyzer


def _get_anonymizer() -> AnonymizerEngine:
    """Get or create Presidio AnonymizerEngine instance."""
    global _anonymizer
    if _anonymizer is None:
        logger.info("Initializing Presidio AnonymizerEngine")
        _anonymizer = AnonymizerEngine()

    return _anonymizer


def add_custom_pattern(pattern: PIIPattern) -> None:
    """
    Add a custom PII detection pattern.

    Args:
        pattern: Custom pattern configuration

    Example:
        >>> pattern = PIIPattern(
        ...     name="company_id",
        ...     entity_type="COMPANY_ID",
        ...     pattern_type="regex",
        ...     pattern=r"COMP-\d{6}",
        ...     score=0.9
        ... )
        >>> add_custom_pattern(pattern)
    """
    global _custom_recognizers

    logger.info(f"Adding custom PII pattern: {pattern.name} ({pattern.entity_type})")

    if pattern.pattern_type == "regex":
        # Regex pattern recognizer
        from presidio_analyzer import Pattern

        recognizer = PatternRecognizer(
            supported_entity=pattern.entity_type,
            patterns=[
                Pattern(
                    name=pattern.name,
                    regex=pattern.pattern if isinstance(pattern.pattern, str) else "",
                    score=pattern.score,
                )
            ],
        )

    elif pattern.pattern_type == "deny_list":
        # Deny list recognizer (exact matches)
        deny_list = (
            pattern.pattern if isinstance(pattern.pattern, list) else [pattern.pattern]
        )
        recognizer = PatternRecognizer(
            supported_entity=pattern.entity_type, deny_list=deny_list
        )

    else:
        logger.warning(f"Unsupported pattern type: {pattern.pattern_type}")
        return

    _custom_recognizers[pattern.name] = recognizer

    # If analyzer already exists, add recognizer to registry
    if _analyzer is not None:
        _analyzer.registry.add_recognizer(recognizer)

    logger.info(f"Custom pattern '{pattern.name}' added successfully")


def remove_custom_pattern(pattern_name: str) -> bool:
    """
    Remove a custom PII detection pattern.

    Args:
        pattern_name: Name of pattern to remove

    Returns:
        True if pattern was removed, False if not found
    """
    global _custom_recognizers

    if pattern_name in _custom_recognizers:
        del _custom_recognizers[pattern_name]
        logger.info(f"Removed custom pattern: {pattern_name}")

        # Note: Presidio doesn't support removing recognizers from registry
        # Restart required for changes to take effect
        logger.warning(
            "Custom recognizer removed from cache. "
            "Restart application to remove from active analyzer."
        )
        return True

    logger.warning(f"Custom pattern not found: {pattern_name}")
    return False


async def detect_pii(
    text: str,
    language: str = "en",
    entities: list[PIIEntityType] | None = None,
    min_score: float = 0.6,
) -> list[PIIDetectionResult]:
    """
    Detect PII entities in text.

    Args:
        text: Text to analyze for PII
        language: Language code (default: 'en')
        entities: Specific entity types to detect (None = detect all)
        min_score: Minimum confidence score threshold

    Returns:
        List of detected PII entities with positions and scores

    Example:
        >>> text = "Contact me at john@example.com or 212-555-5555"
        >>> results = await detect_pii(text)
        >>> print(results)
        [PIIDetectionResult(entity_type='EMAIL_ADDRESS', start=14, end=31, ...)]
    """
    start_time = datetime.utcnow()

    try:
        analyzer = _get_analyzer()

        # Convert entity types to strings
        entity_list = (
            [entity.value for entity in entities]
            if entities
            else None  # None = detect all
        )

        # Run analysis
        logger.debug(
            f"Analyzing text (length={len(text)}) for entities: {entity_list or 'all'}"
        )

        analyzer_results = analyzer.analyze(
            text=text, language=language, entities=entity_list, score_threshold=min_score
        )

        # Convert to our model
        results = []
        for result in analyzer_results:
            # Extract detected text
            detected_text = text[result.start : result.end]

            # Map entity type to our enum (with fallback to original string)
            try:
                entity_type = PIIEntityType(result.entity_type)
            except ValueError:
                # Custom entity type not in enum
                entity_type = PIIEntityType.CUSTOM

            results.append(
                PIIDetectionResult(
                    entity_type=entity_type,
                    start=result.start,
                    end=result.end,
                    score=result.score,
                    text=detected_text,
                )
            )

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            f"PII detection complete: {len(results)} entities found in {processing_time:.2f}ms"
        )

        return results

    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.error(f"PII detection failed after {processing_time:.2f}ms: {e}")
        raise


async def anonymize_text(
    text: str,
    strategy: AnonymizationStrategy = AnonymizationStrategy.REPLACE,
    placeholder: str = "[REDACTED]",
    language: str = "en",
    entities: list[PIIEntityType] | None = None,
    entity_strategies: dict[PIIEntityType, AnonymizationStrategy] | None = None,
    min_score: float = 0.6,
) -> AnonymizationResult:
    """
    Detect and anonymize PII in text.

    Args:
        text: Text to anonymize
        strategy: Default anonymization strategy
        placeholder: Placeholder text for REPLACE strategy
        language: Language code
        entities: Specific entity types to anonymize (None = all)
        entity_strategies: Per-entity anonymization strategies (overrides default)
        min_score: Minimum confidence score threshold

    Returns:
        AnonymizationResult with original text, anonymized text, and detected entities

    Example:
        >>> text = "Email me at john@example.com or call 212-555-5555"
        >>> result = await anonymize_text(text)
        >>> print(result.anonymized_text)
        "Email me at [REDACTED] or call [REDACTED]"
    """
    start_time = datetime.utcnow()

    try:
        # Step 1: Detect PII
        detected_entities = await detect_pii(
            text=text, language=language, entities=entities, min_score=min_score
        )

        if not detected_entities:
            # No PII found
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug(f"No PII detected in text (length={len(text)})")

            return AnonymizationResult(
                original_text=text,
                anonymized_text=text,
                entities_found=[],
                anonymization_applied=False,
                processing_time_ms=processing_time,
            )

        # Step 2: Build operator config for anonymization
        operators: dict[str, OperatorConfig] = {}

        # Default operator
        if strategy == AnonymizationStrategy.REDACT:
            operators["DEFAULT"] = OperatorConfig("redact", {})
        elif strategy == AnonymizationStrategy.REPLACE:
            operators["DEFAULT"] = OperatorConfig(
                "replace", {"new_value": placeholder}
            )
        elif strategy == AnonymizationStrategy.MASK:
            operators["DEFAULT"] = OperatorConfig(
                "mask",
                {
                    "type": "mask",
                    "masking_char": "*",
                    "chars_to_mask": 99,  # Mask all characters
                    "from_end": True,
                },
            )
        elif strategy == AnonymizationStrategy.HASH:
            operators["DEFAULT"] = OperatorConfig("hash", {"hash_type": "sha256"})
        elif strategy == AnonymizationStrategy.KEEP:
            operators["DEFAULT"] = OperatorConfig("keep", {})

        # Per-entity overrides
        if entity_strategies:
            for entity_type, entity_strategy in entity_strategies.items():
                entity_key = entity_type.value

                if entity_strategy == AnonymizationStrategy.REDACT:
                    operators[entity_key] = OperatorConfig("redact", {})
                elif entity_strategy == AnonymizationStrategy.REPLACE:
                    operators[entity_key] = OperatorConfig(
                        "replace", {"new_value": placeholder}
                    )
                elif entity_strategy == AnonymizationStrategy.MASK:
                    # Special handling for phone numbers
                    if entity_type == PIIEntityType.PHONE:
                        operators[entity_key] = OperatorConfig(
                            "mask",
                            {
                                "type": "mask",
                                "masking_char": "*",
                                "chars_to_mask": 12,
                                "from_end": True,
                            },
                        )
                    else:
                        operators[entity_key] = OperatorConfig(
                            "mask",
                            {
                                "type": "mask",
                                "masking_char": "*",
                                "chars_to_mask": 99,
                                "from_end": True,
                            },
                        )
                elif entity_strategy == AnonymizationStrategy.HASH:
                    operators[entity_key] = OperatorConfig(
                        "hash", {"hash_type": "sha256"}
                    )
                elif entity_strategy == AnonymizationStrategy.KEEP:
                    operators[entity_key] = OperatorConfig("keep", {})

        # Step 3: Anonymize text
        anonymizer = _get_anonymizer()

        # Convert detected entities to analyzer results format
        from presidio_anonymizer.entities import RecognizerResult

        analyzer_results = [
            RecognizerResult(
                entity_type=entity.entity_type.value,
                start=entity.start,
                end=entity.end,
                score=entity.score,
            )
            for entity in detected_entities
        ]

        anonymized = anonymizer.anonymize(
            text=text, analyzer_results=analyzer_results, operators=operators
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            f"Text anonymized: {len(detected_entities)} entities processed in {processing_time:.2f}ms"
        )

        return AnonymizationResult(
            original_text=text,
            anonymized_text=anonymized.text,
            entities_found=detected_entities,
            anonymization_applied=True,
            processing_time_ms=processing_time,
        )

    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.error(f"Anonymization failed after {processing_time:.2f}ms: {e}")
        raise


async def anonymize_document_content(
    document_id: str, content: str, title: str = ""
) -> dict[str, Any]:
    """
    Anonymize PII in document content and title.

    This is a convenience function for processing document text.
    Uses settings from app configuration.

    Args:
        document_id: Document identifier for audit logging
        content: Document content text
        title: Document title (optional)

    Returns:
        Dictionary with anonymized_content, anonymized_title, and metadata

    Example:
        >>> result = await anonymize_document_content(
        ...     document_id="doc123",
        ...     content="Contact support at support@example.com",
        ...     title="Support Contact Info"
        ... )
        >>> print(result["anonymized_content"])
        "Contact support at [REDACTED]"
    """
    logger.info(f"Anonymizing document: {document_id}")

    # Anonymize content
    content_result = await anonymize_text(
        text=content,
        strategy=AnonymizationStrategy.REPLACE,
        placeholder="[REDACTED]",
        min_score=settings.pii_min_confidence_score,
    )

    # Anonymize title if provided
    title_result = None
    if title:
        title_result = await anonymize_text(
            text=title,
            strategy=AnonymizationStrategy.REPLACE,
            placeholder="[REDACTED]",
            min_score=settings.pii_min_confidence_score,
        )

    return {
        "document_id": document_id,
        "anonymized_content": content_result.anonymized_text,
        "anonymized_title": title_result.anonymized_text if title_result else title,
        "content_entities_found": len(content_result.entities_found),
        "title_entities_found": (
            len(title_result.entities_found) if title_result else 0
        ),
        "total_entities_found": len(content_result.entities_found)
        + (len(title_result.entities_found) if title_result else 0),
        "anonymization_applied": content_result.anonymization_applied
        or (title_result.anonymization_applied if title_result else False),
        "processing_time_ms": content_result.processing_time_ms
        + (title_result.processing_time_ms if title_result else 0),
    }


async def batch_anonymize(
    texts: list[str],
    strategy: AnonymizationStrategy = AnonymizationStrategy.REPLACE,
    placeholder: str = "[REDACTED]",
) -> list[AnonymizationResult]:
    """
    Anonymize multiple texts in batch.

    Args:
        texts: List of texts to anonymize
        strategy: Anonymization strategy to use
        placeholder: Placeholder text for REPLACE strategy

    Returns:
        List of AnonymizationResult objects

    Example:
        >>> texts = [
        ...     "Email: john@example.com",
        ...     "Phone: 212-555-5555"
        ... ]
        >>> results = await batch_anonymize(texts)
        >>> for result in results:
        ...     print(result.anonymized_text)
    """
    logger.info(f"Batch anonymizing {len(texts)} texts")

    results = []
    for text in texts:
        result = await anonymize_text(
            text=text, strategy=strategy, placeholder=placeholder
        )
        results.append(result)

    total_entities = sum(len(r.entities_found) for r in results)
    total_time = sum(r.processing_time_ms for r in results)

    logger.info(
        f"Batch anonymization complete: {len(texts)} texts, "
        f"{total_entities} entities found in {total_time:.2f}ms"
    )

    return results


def initialize_pii_service() -> None:
    """
    Pre-initialize PII service at application startup.

    This loads the spaCy model and Presidio engines before any requests,
    preventing first-request timeouts and reducing memory pressure.
    """
    logger.info("Pre-initializing PII service at startup")

    # Force initialization of analyzer and anonymizer
    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()

    logger.info(
        f"PII service initialized: analyzer={analyzer is not None}, "
        f"anonymizer={anonymizer is not None}"
    )
