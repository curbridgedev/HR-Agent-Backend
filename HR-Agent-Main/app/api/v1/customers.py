"""
Customer, API Key, and Widget Configuration API endpoints.

Provides REST API for customer management, API key generation,
and widget configuration (Phase 3).
"""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.core.logging import get_logger
from app.models.customers import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerListResponse,
    CustomerDetailsResponse,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListResponse,
    WidgetConfigResponse,
    WidgetConfigUpdateRequest,
    WidgetConfigPublicResponse,
)
from app.services.customers import (
    list_customers,
    create_customer,
    get_customer_details,
    update_customer,
    delete_customer,
    create_api_key,
    list_api_keys,
    delete_api_key,
    get_widget_config,
    upsert_widget_config,
    get_widget_config_by_api_key,
)

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Customer Management Endpoints
# ============================================================================

@router.get("", response_model=CustomerListResponse)
async def get_customers(
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    enabled_only: bool = Query(False, description="Filter for enabled customers only")
):
    """
    List customers with pagination.

    Returns paginated list of customers with basic information.
    Use GET /customers/{id} for detailed view with related data.

    Args:
        limit: Maximum items per page (default: 50, max: 100)
        offset: Number of items to skip for pagination (default: 0)
        enabled_only: Only return enabled customers (default: false)

    Returns:
        Paginated customer list with total count

    Example:
        GET /api/v1/customers?limit=20&offset=0&enabled_only=true
    """
    try:
        logger.info(f"Listing customers: limit={limit}, offset={offset}, enabled_only={enabled_only}")

        customers_response = await list_customers(
            limit=limit,
            offset=offset,
            enabled_only=enabled_only
        )

        return customers_response

    except Exception as e:
        logger.error(f"Failed to list customers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list customers: {str(e)}"
        )


@router.post("", response_model=CustomerDetailsResponse, status_code=status.HTTP_201_CREATED)
async def create_customer_endpoint(request: CustomerCreateRequest):
    """
    Create new customer.

    Creates a new customer with the provided details.
    Email must be unique if provided.

    Args:
        request: Customer creation request with name, email, company, etc.

    Returns:
        Created customer details (201 Created)

    Error Handling:
        - 400 Bad Request: Validation errors
        - 409 Conflict: Email already exists

    Example:
        POST /api/v1/customers
        {
          "name": "Acme Corp",
          "email": "admin@acme.com",
          "company": "Acme Corporation",
          "enabled": true
        }
    """
    try:
        logger.info(f"Creating customer: {request.name}")

        customer = await create_customer(request)

        logger.info(f"Created customer: {customer.id}")
        return customer

    except ValueError as e:
        logger.warning(f"Customer creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create customer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {str(e)}"
        )


@router.get("/{customer_id}", response_model=CustomerDetailsResponse)
async def get_customer(customer_id: UUID):
    """
    Get detailed customer information.

    Returns full customer details including:
    - Basic customer information
    - All API keys (key prefixes only, no full keys)
    - Widget configuration (if exists)

    Args:
        customer_id: Customer UUID

    Returns:
        Customer details with related data

    Error Handling:
        - 404 Not Found: Customer doesn't exist

    Example:
        GET /api/v1/customers/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        logger.info(f"Fetching customer: {customer_id}")

        customer = await get_customer_details(customer_id)

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer not found: {customer_id}"
            )

        return customer

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer: {str(e)}"
        )


@router.patch("/{customer_id}", response_model=CustomerDetailsResponse)
async def update_customer_endpoint(customer_id: UUID, request: CustomerUpdateRequest):
    """
    Update customer details.

    Updates customer information. All fields are optional.
    Email must be unique if provided.

    Args:
        customer_id: Customer UUID
        request: Update request with optional fields

    Returns:
        Updated customer details

    Error Handling:
        - 404 Not Found: Customer doesn't exist
        - 409 Conflict: Email already exists for another customer

    Example:
        PATCH /api/v1/customers/550e8400-e29b-41d4-a716-446655440000
        {
          "enabled": false,
          "metadata": {"reason": "suspended"}
        }
    """
    try:
        logger.info(f"Updating customer: {customer_id}")

        customer = await update_customer(customer_id, request)

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer not found: {customer_id}"
            )

        logger.info(f"Updated customer: {customer_id}")
        return customer

    except ValueError as e:
        logger.warning(f"Customer update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update customer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer: {str(e)}"
        )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_endpoint(customer_id: UUID):
    """
    Delete customer and all associated data.

    Permanently deletes customer including:
    - All API keys (CASCADE)
    - Widget configuration (CASCADE)

    IMPORTANT: This is a hard delete operation.

    Args:
        customer_id: Customer UUID

    Returns:
        No content (204) on success

    Error Handling:
        - 404 Not Found: Customer doesn't exist

    Example:
        DELETE /api/v1/customers/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        logger.info(f"Deleting customer: {customer_id}")

        deleted = await delete_customer(customer_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer not found: {customer_id}"
            )

        logger.info(f"Deleted customer: {customer_id}")
        # FastAPI automatically returns 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete customer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete customer: {str(e)}"
        )


# ============================================================================
# API Key Management Endpoints
# ============================================================================

@router.post(
    "/{customer_id}/api-keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_api_key_endpoint(customer_id: UUID, request: APIKeyCreateRequest):
    """
    Generate new API key for customer.

    Creates a cryptographically secure API key with format:
    - Production: cp_live_<32_random_hex_chars>
    - Test: cp_test_<32_random_hex_chars>

    ⚠️ CRITICAL: Full API key is ONLY shown in this response!
    It will never be displayed again. Store it securely.

    Args:
        customer_id: Customer UUID
        request: API key creation request with optional name and limits

    Returns:
        Created API key with full key (201 Created)

    Error Handling:
        - 404 Not Found: Customer doesn't exist
        - 400 Bad Request: Customer is disabled

    Example:
        POST /api/v1/customers/{id}/api-keys
        {
          "name": "Production Widget",
          "rate_limit_per_minute": 100,
          "rate_limit_per_day": 50000
        }

        Response:
        {
          "id": "...",
          "api_key": "cp_live_abc123...",  ⚠️ ONLY SHOWN ONCE!
          "key_prefix": "cp_live_abc12345",
          ...
        }
    """
    try:
        logger.info(f"Creating API key for customer: {customer_id}")

        api_key = await create_api_key(customer_id, request)

        logger.info(f"Created API key: {api_key.id} for customer: {customer_id}")
        return api_key

    except ValueError as e:
        logger.warning(f"API key creation failed: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        logger.error(f"Failed to create API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get("/{customer_id}/api-keys", response_model=APIKeyListResponse)
async def get_api_keys(customer_id: UUID):
    """
    List all API keys for customer.

    Returns all API keys with key prefixes (first 16 chars).
    Full keys are never returned after creation.

    Args:
        customer_id: Customer UUID

    Returns:
        List of API keys (no full keys)

    Error Handling:
        - 404 Not Found: Customer doesn't exist

    Example:
        GET /api/v1/customers/550e8400-e29b-41d4-a716-446655440000/api-keys
    """
    try:
        logger.info(f"Listing API keys for customer: {customer_id}")

        api_keys_response = await list_api_keys(customer_id)

        return api_keys_response

    except ValueError as e:
        logger.warning(f"List API keys failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.delete(
    "/{customer_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_api_key_endpoint(customer_id: UUID, key_id: UUID):
    """
    Revoke (delete) API key.

    Permanently deletes API key. Widget authentication will fail
    immediately for this key.

    Args:
        customer_id: Customer UUID
        key_id: API key UUID

    Returns:
        No content (204) on success

    Error Handling:
        - 404 Not Found: Customer or key doesn't exist

    Example:
        DELETE /api/v1/customers/{customer_id}/api-keys/{key_id}
    """
    try:
        logger.info(f"Deleting API key: {key_id} for customer: {customer_id}")

        deleted = await delete_api_key(customer_id, key_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key not found: {key_id}"
            )

        logger.info(f"Deleted API key: {key_id}")
        # FastAPI automatically returns 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete API key: {str(e)}"
        )


# ============================================================================
# Widget Configuration Endpoints
# ============================================================================

@router.get("/{customer_id}/widget-config", response_model=WidgetConfigResponse)
async def get_widget_config_endpoint(customer_id: UUID):
    """
    Get widget configuration for customer.

    Returns widget configuration including theme, position,
    greeting message, and other display settings.

    Args:
        customer_id: Customer UUID

    Returns:
        Widget configuration

    Error Handling:
        - 404 Not Found: Customer doesn't exist or no widget config

    Example:
        GET /api/v1/customers/550e8400-e29b-41d4-a716-446655440000/widget-config
    """
    try:
        logger.info(f"Fetching widget config for customer: {customer_id}")

        widget_config = await get_widget_config(customer_id)

        if not widget_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Widget config not found for customer: {customer_id}"
            )

        return widget_config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get widget config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get widget config: {str(e)}"
        )


@router.put("/{customer_id}/widget-config", response_model=WidgetConfigResponse)
async def upsert_widget_config_endpoint(
    customer_id: UUID,
    request: WidgetConfigUpdateRequest
):
    """
    Create or update widget configuration (upsert).

    Creates new widget config or updates existing one.
    Uses PostgreSQL UPSERT (ON CONFLICT customer_id DO UPDATE).

    Args:
        customer_id: Customer UUID
        request: Widget config update request (all fields optional)

    Returns:
        Created/updated widget configuration (200 OK or 201 Created)

    Error Handling:
        - 404 Not Found: Customer doesn't exist
        - 400 Bad Request: Validation errors (invalid domains, etc.)

    Example:
        PUT /api/v1/customers/{id}/widget-config
        {
          "position": "bottom-right",
          "theme_config": {
            "primaryColor": "#3B82F6",
            "fontFamily": "Inter, sans-serif"
          },
          "greeting_message": "Hello! How can we help?",
          "auto_open": true,
          "auto_open_delay": 5
        }
    """
    try:
        logger.info(f"Upserting widget config for customer: {customer_id}")

        widget_config = await upsert_widget_config(customer_id, request)

        logger.info(f"Upserted widget config for customer: {customer_id}")
        return widget_config

    except ValueError as e:
        logger.warning(f"Widget config upsert failed: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        logger.error(f"Failed to upsert widget config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upsert widget config: {str(e)}"
        )


# ============================================================================
# Public Widget Configuration Endpoint (by API key)
# NOTE: This endpoint is moved to a separate router and registered at root level
# Path: GET /api/v1/widget-config/by-api-key/{api_key}
# See: app/api/v1/widget.py
# ============================================================================
