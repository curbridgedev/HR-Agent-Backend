"""
Customer management service layer.

Business logic for customer CRUD operations, API key generation,
and widget configuration management.
"""

import secrets
import hashlib
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from supabase import Client

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.customers import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerListResponse,
    CustomerListItem,
    CustomerDetailsResponse,
    APIKeyBase,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListResponse,
    WidgetConfigResponse,
    WidgetConfigUpdateRequest,
    WidgetConfigPublicResponse,
    ThemeConfig,
)

logger = get_logger(__name__)


# ============================================================================
# Customer Management
# ============================================================================

async def list_customers(
    limit: int = 50,
    offset: int = 0,
    enabled_only: bool = False,
    db: Optional[Client] = None,
) -> CustomerListResponse:
    """
    List customers with pagination.

    Args:
        limit: Maximum items per page (default: 50)
        offset: Number of items to skip (default: 0)
        enabled_only: Filter for enabled customers only
        db: Optional Supabase client

    Returns:
        Paginated customer list
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Listing customers: limit={limit}, offset={offset}, enabled_only={enabled_only}")

        # Build query
        query = db.table("customers").select("*", count="exact")

        # Note: 'enabled' column doesn't exist in DB, skip filter
        # if enabled_only:
        #     query = query.eq("enabled", True)

        # Execute with pagination
        response = query.order("created_at", desc=True).range(
            offset, offset + limit - 1
        ).execute()

        # Map database columns to model fields
        customers = [
            CustomerListItem(
                id=c['id'],
                name=c.get('full_name', ''),
                email=c.get('email'),
                company=c.get('company_name'),
                enabled=True,  # No enabled column in DB
                metadata=c.get('metadata', {}),
                created_at=c['created_at'],
                updated_at=c.get('updated_at')
            )
            for c in response.data
        ]

        return CustomerListResponse(
            customers=customers,
            total_count=response.count if response.count is not None else 0,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to list customers: {e}", exc_info=True)
        raise


async def create_customer(
    request: CustomerCreateRequest,
    db: Optional[Client] = None,
) -> CustomerDetailsResponse:
    """
    Create new customer.

    Args:
        request: Customer creation request
        db: Optional Supabase client

    Returns:
        Created customer details

    Raises:
        ValueError: If email already exists
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Creating customer: {request.name}")

        # Check for duplicate email
        if request.email:
            existing = db.table("customers").select("id").eq("email", request.email).execute()
            if existing.data:
                raise ValueError(f"Customer with email {request.email} already exists")

        # Insert customer (map 'company' to 'company_name' for database)
        response = db.table("customers").insert({
            "full_name": request.name,
            "email": request.email,
            "company_name": request.company,
            "metadata": request.metadata,
        }).execute()

        if not response.data:
            raise ValueError("Failed to create customer")

        customer_data = response.data[0]
        logger.info(f"Created customer: {customer_data['id']}")

        # Map database columns to model fields
        return CustomerDetailsResponse(
            id=customer_data['id'],
            name=customer_data.get('full_name', ''),
            email=customer_data.get('email'),
            company=customer_data.get('company_name'),
            enabled=True,  # No enabled column in DB, default to True
            metadata=customer_data.get('metadata', {}),
            created_at=customer_data['created_at'],
            updated_at=customer_data.get('updated_at'),
            api_keys=[],
            widget_config=None
        )

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to create customer: {e}", exc_info=True)
        raise


async def get_customer_details(
    customer_id: UUID,
    db: Optional[Client] = None,
) -> Optional[CustomerDetailsResponse]:
    """
    Get detailed customer information with API keys and widget config.

    Args:
        customer_id: Customer UUID
        db: Optional Supabase client

    Returns:
        Customer details with related data, or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Fetching customer details: {customer_id}")

        # Get customer
        customer_response = db.table("customers").select("*").eq(
            "id", str(customer_id)
        ).execute()

        if not customer_response.data:
            return None

        customer_data = customer_response.data[0]

        # Get API keys (no full key hash)
        api_keys_response = db.table("customer_api_keys").select("*").eq(
            "customer_id", str(customer_id)
        ).execute()

        api_keys = [APIKeyBase(**key) for key in api_keys_response.data]

        # Get widget config
        widget_response = db.table("widget_configs").select("*").eq(
            "customer_id", str(customer_id)
        ).execute()

        widget_config = None
        if widget_response.data:
            widget_data = widget_response.data[0]
            widget_config = WidgetConfigResponse(**widget_data)

        # Map database columns to model fields
        return CustomerDetailsResponse(
            id=customer_data['id'],
            name=customer_data.get('full_name', ''),
            email=customer_data.get('email'),
            company=customer_data.get('company_name'),
            enabled=True,  # No enabled column in DB
            metadata=customer_data.get('metadata', {}),
            created_at=customer_data['created_at'],
            updated_at=customer_data.get('updated_at'),
            api_keys=api_keys,
            widget_config=widget_config
        )

    except Exception as e:
        logger.error(f"Failed to get customer details: {e}", exc_info=True)
        raise


async def update_customer(
    customer_id: UUID,
    request: CustomerUpdateRequest,
    db: Optional[Client] = None,
) -> Optional[CustomerDetailsResponse]:
    """
    Update customer details.

    Args:
        customer_id: Customer UUID
        request: Update request with optional fields
        db: Optional Supabase client

    Returns:
        Updated customer details, or None if not found

    Raises:
        ValueError: If email already exists for another customer
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Updating customer: {customer_id}")

        # Check if customer exists
        existing = db.table("customers").select("id").eq("id", str(customer_id)).execute()
        if not existing.data:
            return None

        # Build update dict (map to correct column names)
        update_data = {}
        if request.name is not None:
            update_data["full_name"] = request.name
        if request.email is not None:
            # Check for duplicate email
            dup_check = db.table("customers").select("id").eq("email", request.email).neq(
                "id", str(customer_id)
            ).execute()
            if dup_check.data:
                raise ValueError(f"Customer with email {request.email} already exists")
            update_data["email"] = request.email
        if request.company is not None:
            update_data["company_name"] = request.company
        # Note: enabled column doesn't exist in DB, skip it
        # if request.enabled is not None:
        #     update_data["enabled"] = request.enabled
        if request.metadata is not None:
            update_data["metadata"] = request.metadata

        if not update_data:
            # No updates provided, return current data
            return await get_customer_details(customer_id, db)

        # Update timestamp
        update_data["updated_at"] = datetime.utcnow().isoformat()

        # Execute update
        db.table("customers").update(update_data).eq("id", str(customer_id)).execute()

        logger.info(f"Updated customer: {customer_id}")

        # Return updated details
        return await get_customer_details(customer_id, db)

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to update customer: {e}", exc_info=True)
        raise


async def delete_customer(
    customer_id: UUID,
    db: Optional[Client] = None,
) -> bool:
    """
    Delete customer and all associated data (CASCADE).

    Args:
        customer_id: Customer UUID
        db: Optional Supabase client

    Returns:
        True if deleted, False if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Deleting customer: {customer_id}")

        # Check if exists
        existing = db.table("customers").select("id").eq("id", str(customer_id)).execute()
        if not existing.data:
            return False

        # Delete (CASCADE will delete API keys and widget config)
        db.table("customers").delete().eq("id", str(customer_id)).execute()

        logger.info(f"Deleted customer: {customer_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete customer: {e}", exc_info=True)
        raise


# ============================================================================
# API Key Management
# ============================================================================

def _generate_api_key(environment: str = "live") -> tuple[str, str, str]:
    """
    Generate cryptographically secure API key.

    Args:
        environment: "live" or "test"

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
        - full_key: Complete key (e.g., "cp_live_abc123...")
        - key_prefix: First 16 chars for display
        - key_hash: SHA-256 hash for storage
    """
    # Generate 32 random hex characters
    random_suffix = secrets.token_hex(16)

    # Format: cp_live_<32_chars> or cp_test_<32_chars>
    prefix = "cp_live" if environment == "live" else "cp_test"
    full_key = f"{prefix}_{random_suffix}"

    # Key prefix for display (first 16 chars)
    key_prefix = full_key[:16]

    # SHA-256 hash for storage
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    return full_key, key_prefix, key_hash


async def create_api_key(
    customer_id: UUID,
    request: APIKeyCreateRequest,
    db: Optional[Client] = None,
) -> APIKeyCreateResponse:
    """
    Generate new API key for customer.

    Args:
        customer_id: Customer UUID
        request: API key creation request
        db: Optional Supabase client

    Returns:
        Created API key with full key (shown once only)

    Raises:
        ValueError: If customer not found or disabled
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Creating API key for customer: {customer_id}")

        # Check if customer exists and is enabled
        customer_response = db.table("customers").select("enabled").eq(
            "id", str(customer_id)
        ).execute()

        if not customer_response.data:
            raise ValueError(f"Customer not found: {customer_id}")

        if not customer_response.data[0]["enabled"]:
            raise ValueError("Cannot create API key for disabled customer")

        # Generate API key
        full_key, key_prefix, key_hash = _generate_api_key(environment="live")

        # Insert into database
        response = db.table("customer_api_keys").insert({
            "customer_id": str(customer_id),
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "name": request.name,
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "rate_limit_per_minute": request.rate_limit_per_minute,
            "rate_limit_per_day": request.rate_limit_per_day,
            "enabled": True,
        }).execute()

        if not response.data:
            raise ValueError("Failed to create API key")

        key_data = response.data[0]
        logger.info(f"Created API key: {key_data['id']} (prefix: {key_prefix})")

        # Return with full key (ONLY TIME IT'S SHOWN)
        return APIKeyCreateResponse(
            **key_data,
            api_key=full_key  # ⚠️ CRITICAL: Only in this response!
        )

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to create API key: {e}", exc_info=True)
        raise


async def list_api_keys(
    customer_id: UUID,
    db: Optional[Client] = None,
) -> APIKeyListResponse:
    """
    List all API keys for customer.

    Args:
        customer_id: Customer UUID
        db: Optional Supabase client

    Returns:
        List of API keys (no full keys)

    Raises:
        ValueError: If customer not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Listing API keys for customer: {customer_id}")

        # Check if customer exists
        customer_response = db.table("customers").select("id").eq(
            "id", str(customer_id)
        ).execute()

        if not customer_response.data:
            raise ValueError(f"Customer not found: {customer_id}")

        # Get API keys
        response = db.table("customer_api_keys").select("*").eq(
            "customer_id", str(customer_id)
        ).order("created_at", desc=True).execute()

        api_keys = [APIKeyBase(**key) for key in response.data]

        return APIKeyListResponse(
            api_keys=api_keys,
            total_count=len(api_keys)
        )

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}", exc_info=True)
        raise


async def delete_api_key(
    customer_id: UUID,
    key_id: UUID,
    db: Optional[Client] = None,
) -> bool:
    """
    Revoke (delete) API key.

    Args:
        customer_id: Customer UUID
        key_id: API key UUID
        db: Optional Supabase client

    Returns:
        True if deleted, False if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Deleting API key: {key_id} for customer: {customer_id}")

        # Check if key exists for this customer
        existing = db.table("customer_api_keys").select("id").eq(
            "id", str(key_id)
        ).eq("customer_id", str(customer_id)).execute()

        if not existing.data:
            return False

        # Delete key
        db.table("customer_api_keys").delete().eq("id", str(key_id)).execute()

        logger.info(f"Deleted API key: {key_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete API key: {e}", exc_info=True)
        raise


# ============================================================================
# Widget Configuration
# ============================================================================

async def get_widget_config(
    customer_id: UUID,
    db: Optional[Client] = None,
) -> Optional[WidgetConfigResponse]:
    """
    Get widget configuration for customer.

    Args:
        customer_id: Customer UUID
        db: Optional Supabase client

    Returns:
        Widget configuration, or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Fetching widget config for customer: {customer_id}")

        # Check if customer exists
        customer_response = db.table("customers").select("id").eq(
            "id", str(customer_id)
        ).execute()

        if not customer_response.data:
            return None

        # Get widget config
        response = db.table("widget_configs").select("*").eq(
            "customer_id", str(customer_id)
        ).execute()

        if not response.data:
            return None

        return WidgetConfigResponse(**response.data[0])

    except Exception as e:
        logger.error(f"Failed to get widget config: {e}", exc_info=True)
        raise


async def upsert_widget_config(
    customer_id: UUID,
    request: WidgetConfigUpdateRequest,
    db: Optional[Client] = None,
) -> WidgetConfigResponse:
    """
    Create or update widget configuration (upsert).

    Args:
        customer_id: Customer UUID
        request: Widget config update request
        db: Optional Supabase client

    Returns:
        Created/updated widget configuration

    Raises:
        ValueError: If customer not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info(f"Upserting widget config for customer: {customer_id}")

        # Check if customer exists
        customer_response = db.table("customers").select("id").eq(
            "id", str(customer_id)
        ).execute()

        if not customer_response.data:
            raise ValueError(f"Customer not found: {customer_id}")

        # Build upsert data (only provided fields)
        upsert_data = {"customer_id": str(customer_id)}

        if request.position is not None:
            upsert_data["position"] = request.position
        if request.auto_open is not None:
            upsert_data["auto_open"] = request.auto_open
        if request.auto_open_delay is not None:
            upsert_data["auto_open_delay"] = request.auto_open_delay
        if request.theme_config is not None:
            upsert_data["theme_config"] = request.theme_config.dict()
        if request.greeting_message is not None:
            upsert_data["greeting_message"] = request.greeting_message
        if request.placeholder_text is not None:
            upsert_data["placeholder_text"] = request.placeholder_text
        if request.logo_url is not None:
            upsert_data["logo_url"] = request.logo_url
        if request.company_name is not None:
            upsert_data["company_name"] = request.company_name
        if request.allowed_domains is not None:
            upsert_data["allowed_domains"] = request.allowed_domains
        if request.max_history_messages is not None:
            upsert_data["max_history_messages"] = request.max_history_messages
        if request.show_confidence_scores is not None:
            upsert_data["show_confidence_scores"] = request.show_confidence_scores

        # Update timestamp
        upsert_data["updated_at"] = datetime.utcnow().isoformat()

        # Upsert (ON CONFLICT customer_id DO UPDATE)
        response = db.table("widget_configs").upsert(
            upsert_data,
            on_conflict="customer_id"
        ).execute()

        if not response.data:
            raise ValueError("Failed to upsert widget config")

        logger.info(f"Upserted widget config for customer: {customer_id}")
        return WidgetConfigResponse(**response.data[0])

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert widget config: {e}", exc_info=True)
        raise


async def get_widget_config_by_api_key(
    api_key: str,
    db: Optional[Client] = None,
) -> Optional[WidgetConfigPublicResponse]:
    """
    Get widget configuration by API key (PUBLIC endpoint).

    Args:
        api_key: Full API key (e.g., "cp_live_abc123...")
        db: Optional Supabase client

    Returns:
        Public widget configuration (no sensitive data), or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        logger.info("Fetching widget config by API key (public)")

        # Hash the provided API key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Find API key
        key_response = db.table("customer_api_keys").select("customer_id,enabled").eq(
            "key_hash", key_hash
        ).execute()

        if not key_response.data:
            logger.warning("API key not found")
            return None

        key_data = key_response.data[0]

        if not key_data["enabled"]:
            logger.warning("API key is disabled")
            return None

        # Get widget config for this customer
        customer_id = key_data["customer_id"]
        widget_response = db.table("widget_configs").select("*").eq(
            "customer_id", customer_id
        ).execute()

        if not widget_response.data:
            logger.info(f"No widget config for customer: {customer_id}")
            return None

        widget_data = widget_response.data[0]

        # Return public response (no sensitive fields)
        return WidgetConfigPublicResponse(
            position=widget_data["position"],
            auto_open=widget_data["auto_open"],
            auto_open_delay=widget_data["auto_open_delay"],
            theme_config=ThemeConfig(**widget_data["theme_config"]),
            greeting_message=widget_data["greeting_message"],
            placeholder_text=widget_data["placeholder_text"],
            logo_url=widget_data.get("logo_url"),
            company_name=widget_data.get("company_name"),
            allowed_domains=widget_data.get("allowed_domains"),
            max_history_messages=widget_data["max_history_messages"],
            show_confidence_scores=widget_data["show_confidence_scores"],
        )

    except Exception as e:
        logger.error(f"Failed to get widget config by API key: {e}", exc_info=True)
        raise
