"""
OAuth token endpoint for programmatic API access.

Allows users to exchange email/password credentials for a bearer token
(OAuth 2.0 Resource Owner Password Credentials grant).
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Auth"])


# ============================================================================
# Request/Response Models
# ============================================================================


class TokenRequest(BaseModel):
    """OAuth 2.0 Resource Owner Password Credentials request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    """OAuth 2.0 token response."""

    access_token: str = Field(..., description="JWT bearer token for API authentication")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    refresh_token: str | None = Field(None, description="Refresh token for obtaining new access tokens")


# ============================================================================
# Token Endpoint
# ============================================================================


@router.post("/token", response_model=TokenResponse)
async def get_token(request: TokenRequest) -> TokenResponse:
    """
    Exchange email and password for a bearer token.

    Use this endpoint for programmatic API access and Swagger Try it out.
    Returns a Supabase JWT that can be used in the `Authorization: Bearer <token>` header.
    After getting the token, click Authorize in Swagger and enter: Bearer <your_token>

    **Alternative:** Use X-API-Key header with a personal API key from Settings > API Keys.

    **Note:** Only works for users who signed up with email/password.
    Google SSO users must use the web login flow to obtain a token, or use X-API-Key from Settings.
    """
    try:
        from supabase import create_client

        # Use anon key for auth operations (sign_in_with_password)
        auth_client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_anon_key,
        )

        response = auth_client.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )

        if not response.session:
            logger.warning(f"Sign-in failed for {request.email}: no session returned")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        session = response.session
        user = response.user

        # Check if user is active
        user_metadata = user.user_metadata or {}
        is_active = user_metadata.get("is_active", True)
        if not is_active:
            logger.warning(f"Inactive user attempted token exchange: {user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact an administrator.",
            )

        # Supabase JWT expiry is in seconds (exp claim is Unix timestamp)
        expires_in = session.expires_in or 3600

        return TokenResponse(
            access_token=session.access_token,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=session.refresh_token,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token exchange failed for {request.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
