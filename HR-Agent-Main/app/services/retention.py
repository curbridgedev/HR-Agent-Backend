"""
Data retention and GDPR compliance service.

This service implements:
- Configurable data retention policies
- Automatic deletion workflows
- Right-to-be-forgotten (GDPR Article 17)
- Audit logging for all deletion operations

Retention policies define how long data should be kept before automatic deletion.
GDPR utilities allow users to request deletion of their personal data.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client

logger = get_logger(__name__)


class RetentionPolicy:
    """Data retention policy configuration."""

    def __init__(
        self,
        name: str,
        description: str,
        retention_days: int,
        applies_to_sources: list[str] | None = None,
        auto_delete: bool = True,
    ):
        self.name = name
        self.description = description
        self.retention_days = retention_days
        self.applies_to_sources = applies_to_sources or []  # Empty = all sources
        self.auto_delete = auto_delete

    def __repr__(self) -> str:
        return (
            f"RetentionPolicy(name={self.name}, "
            f"retention_days={self.retention_days}, "
            f"auto_delete={self.auto_delete})"
        )


# Default retention policies
DEFAULT_POLICIES = [
    RetentionPolicy(
        name="chat_messages",
        description="Chat messages from Slack, WhatsApp, Telegram",
        retention_days=365,  # 1 year
        applies_to_sources=["slack", "whatsapp", "telegram"],
        auto_delete=True,
    ),
    RetentionPolicy(
        name="admin_uploads",
        description="Documents uploaded by admins",
        retention_days=730,  # 2 years
        applies_to_sources=["admin_upload"],
        auto_delete=False,  # Manual deletion only
    ),
    RetentionPolicy(
        name="audit_logs",
        description="System audit logs and deletion records",
        retention_days=2555,  # 7 years (compliance requirement)
        applies_to_sources=["audit"],
        auto_delete=False,
    ),
]


async def get_retention_policy_for_source(source: str) -> RetentionPolicy | None:
    """
    Get the retention policy that applies to a given source.

    Args:
        source: Source identifier (slack, whatsapp, telegram, admin_upload)

    Returns:
        Applicable RetentionPolicy or None if no policy applies
    """
    for policy in DEFAULT_POLICIES:
        # Empty list means applies to all sources
        if not policy.applies_to_sources or source in policy.applies_to_sources:
            return policy

    return None


async def get_documents_for_deletion(
    retention_policy: RetentionPolicy,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """
    Get documents that are eligible for deletion based on retention policy.

    Args:
        retention_policy: Retention policy to apply
        dry_run: If True, only return documents without deleting

    Returns:
        List of document dictionaries eligible for deletion

    Example:
        >>> policy = DEFAULT_POLICIES[0]  # chat_messages
        >>> docs = await get_documents_for_deletion(policy, dry_run=True)
        >>> print(f"Found {len(docs)} documents eligible for deletion")
    """
    supabase = get_supabase_client()

    # Calculate cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=retention_policy.retention_days)

    logger.info(
        f"Finding documents for deletion: policy={retention_policy.name}, "
        f"cutoff_date={cutoff_date.isoformat()}, dry_run={dry_run}"
    )

    try:
        # Build query
        query = (
            supabase.table("documents")
            .select("id, source, title, normalized_timestamp, created_at")
            .lt("normalized_timestamp", cutoff_date.isoformat())
        )

        # Filter by sources if policy specifies
        if retention_policy.applies_to_sources:
            query = query.in_("source", retention_policy.applies_to_sources)

        response = query.execute()

        documents = response.data or []

        logger.info(
            f"Found {len(documents)} documents eligible for deletion "
            f"(retention_policy={retention_policy.name})"
        )

        return documents

    except Exception as e:
        logger.error(f"Error finding documents for deletion: {e}")
        raise


async def delete_documents_by_retention_policy(
    retention_policy: RetentionPolicy,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Delete documents based on retention policy.

    Args:
        retention_policy: Retention policy to apply
        dry_run: If True, simulate deletion without actually deleting

    Returns:
        Dictionary with deletion results and audit information

    Example:
        >>> policy = DEFAULT_POLICIES[0]
        >>> result = await delete_documents_by_retention_policy(policy, dry_run=False)
        >>> print(f"Deleted {result['documents_deleted']} documents")
    """
    start_time = datetime.utcnow()
    supabase = get_supabase_client()

    logger.info(
        f"Starting retention-based deletion: policy={retention_policy.name}, dry_run={dry_run}"
    )

    # Get documents eligible for deletion
    documents = await get_documents_for_deletion(retention_policy, dry_run=dry_run)

    if not documents:
        logger.info("No documents eligible for deletion")
        return {
            "documents_deleted": 0,
            "dry_run": dry_run,
            "policy_name": retention_policy.name,
            "processing_time_ms": 0,
            "audit_log_created": False,
        }

    documents_deleted = 0

    if not dry_run:
        # Actually delete documents
        try:
            document_ids = [doc["id"] for doc in documents]

            # Delete in batches of 100
            batch_size = 100
            for i in range(0, len(document_ids), batch_size):
                batch = document_ids[i : i + batch_size]
                supabase.table("documents").delete().in_("id", batch).execute()
                documents_deleted += len(batch)

            logger.info(f"Deleted {documents_deleted} documents")

            # Create audit log entry
            audit_entry = {
                "operation": "retention_deletion",
                "policy_name": retention_policy.name,
                "documents_deleted": documents_deleted,
                "cutoff_date": (
                    datetime.utcnow()
                    - timedelta(days=retention_policy.retention_days)
                ).isoformat(),
                "performed_at": datetime.utcnow().isoformat(),
                "performed_by": "system:retention_service",
                "metadata": {
                    "retention_days": retention_policy.retention_days,
                    "applies_to_sources": retention_policy.applies_to_sources,
                    "document_ids": document_ids[:100],  # Store first 100 IDs
                },
            }

            # Note: This would be stored in a dedicated audit_logs table
            # For now, we'll just log it
            logger.info(f"Audit log created: {audit_entry}")

        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise

    processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

    return {
        "documents_deleted": documents_deleted,
        "documents_found": len(documents),
        "dry_run": dry_run,
        "policy_name": retention_policy.name,
        "processing_time_ms": processing_time,
        "audit_log_created": not dry_run,
    }


async def delete_user_data(
    user_identifier: str,
    identifier_type: str = "author_id",
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Delete all data associated with a specific user (GDPR Right to be Forgotten).

    This implements GDPR Article 17 - Right to Erasure.

    Args:
        user_identifier: User identifier (email, author_id, phone number, etc.)
        identifier_type: Type of identifier (author_id, email, phone, etc.)
        dry_run: If True, simulate deletion without actually deleting

    Returns:
        Dictionary with deletion results and audit information

    Example:
        >>> result = await delete_user_data(
        ...     user_identifier="user123@slack",
        ...     identifier_type="author_id",
        ...     dry_run=False
        ... )
        >>> print(f"Deleted {result['documents_deleted']} documents")
    """
    start_time = datetime.utcnow()
    supabase = get_supabase_client()

    logger.info(
        f"GDPR deletion request: user={user_identifier}, "
        f"type={identifier_type}, dry_run={dry_run}"
    )

    try:
        # Find all documents by this user
        query = supabase.table("documents").select("id, source, title, created_at")

        # Filter by identifier type
        if identifier_type == "author_id":
            query = query.eq("author_id", user_identifier)
        elif identifier_type == "email":
            # Search in author_name or metadata
            query = query.or_(
                f"author_name.ilike.%{user_identifier}%,"
                f"metadata->>email.eq.{user_identifier}"
            )
        elif identifier_type == "phone":
            # Search in metadata
            query = query.contains("metadata", {"phone": user_identifier})
        else:
            logger.warning(f"Unknown identifier type: {identifier_type}")
            return {
                "documents_deleted": 0,
                "error": f"Unknown identifier type: {identifier_type}",
            }

        response = query.execute()
        documents = response.data or []

        logger.info(
            f"Found {len(documents)} documents for user {user_identifier} "
            f"(identifier_type={identifier_type})"
        )

        documents_deleted = 0

        if not dry_run and documents:
            # Actually delete documents
            document_ids = [doc["id"] for doc in documents]

            # Delete in batches of 100
            batch_size = 100
            for i in range(0, len(document_ids), batch_size):
                batch = document_ids[i : i + batch_size]
                supabase.table("documents").delete().in_("id", batch).execute()
                documents_deleted += len(batch)

            logger.info(
                f"GDPR deletion complete: deleted {documents_deleted} documents "
                f"for user {user_identifier}"
            )

            # Create audit log entry
            audit_entry = {
                "operation": "gdpr_deletion",
                "user_identifier": user_identifier,
                "identifier_type": identifier_type,
                "documents_deleted": documents_deleted,
                "performed_at": datetime.utcnow().isoformat(),
                "performed_by": "system:gdpr_service",
                "metadata": {
                    "document_ids": document_ids[:100],  # Store first 100 IDs
                    "legal_basis": "GDPR Article 17 - Right to Erasure",
                },
            }

            logger.info(f"GDPR audit log created: {audit_entry}")

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return {
            "documents_deleted": documents_deleted,
            "documents_found": len(documents),
            "user_identifier": user_identifier,
            "identifier_type": identifier_type,
            "dry_run": dry_run,
            "processing_time_ms": processing_time,
            "audit_log_created": not dry_run,
            "legal_basis": "GDPR Article 17 - Right to Erasure",
        }

    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.error(
            f"GDPR deletion failed after {processing_time:.2f}ms "
            f"for user {user_identifier}: {e}"
        )
        raise


async def get_retention_statistics() -> dict[str, Any]:
    """
    Get statistics about documents and retention policies.

    Returns:
        Dictionary with retention statistics

    Example:
        >>> stats = await get_retention_statistics()
        >>> print(f"Total documents: {stats['total_documents']}")
        >>> print(f"Eligible for deletion: {stats['eligible_for_deletion']}")
    """
    supabase = get_supabase_client()

    try:
        # Get total document count
        total_response = (
            supabase.table("documents").select("id", count="exact").execute()
        )
        total_documents = total_response.count or 0

        # Get documents eligible for deletion per policy
        policy_stats = []

        for policy in DEFAULT_POLICIES:
            if not policy.auto_delete:
                continue

            eligible_docs = await get_documents_for_deletion(policy, dry_run=True)

            policy_stats.append(
                {
                    "policy_name": policy.name,
                    "retention_days": policy.retention_days,
                    "eligible_for_deletion": len(eligible_docs),
                    "applies_to_sources": policy.applies_to_sources,
                    "auto_delete": policy.auto_delete,
                }
            )

        total_eligible = sum(stat["eligible_for_deletion"] for stat in policy_stats)

        return {
            "total_documents": total_documents,
            "eligible_for_deletion": total_eligible,
            "policies": policy_stats,
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting retention statistics: {e}")
        raise
