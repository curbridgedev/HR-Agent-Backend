"""
Encryption utilities for sensitive configuration data.

Uses Fernet symmetric encryption for API keys and secrets.
"""

from typing import Optional
from cryptography.fernet import Fernet
import base64
import hashlib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_encryption_key() -> bytes:
    """
    Derive encryption key from SECRET_KEY.

    Uses SHA-256 to create a consistent 32-byte key from the secret.

    Returns:
        32-byte encryption key suitable for Fernet
    """
    # Use SHA-256 to derive a consistent key from SECRET_KEY
    key_material = settings.secret_key.encode()
    derived_key = hashlib.sha256(key_material).digest()

    # Fernet requires base64-encoded 32-byte key
    return base64.urlsafe_b64encode(derived_key)


def encrypt_value(value: str) -> str:
    """
    Encrypt a sensitive value (e.g., API key).

    Args:
        value: Plain text value to encrypt

    Returns:
        Base64-encoded encrypted value

    Raises:
        ValueError: If value is empty
        Exception: If encryption fails
    """
    if not value or not value.strip():
        raise ValueError("Cannot encrypt empty value")

    try:
        encryption_key = _get_encryption_key()
        fernet = Fernet(encryption_key)

        # Encrypt and return as string
        encrypted_bytes = fernet.encrypt(value.encode())
        return encrypted_bytes.decode()

    except Exception as e:
        logger.error(f"Encryption failed: {e}", exc_info=True)
        raise


def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt a sensitive value.

    Args:
        encrypted_value: Base64-encoded encrypted value

    Returns:
        Decrypted plain text value

    Raises:
        ValueError: If encrypted_value is empty or invalid
        Exception: If decryption fails
    """
    if not encrypted_value or not encrypted_value.strip():
        raise ValueError("Cannot decrypt empty value")

    try:
        encryption_key = _get_encryption_key()
        fernet = Fernet(encryption_key)

        # Decrypt and return as string
        decrypted_bytes = fernet.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()

    except Exception as e:
        logger.error(f"Decryption failed: {e}", exc_info=True)
        raise


def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive value for display.

    Shows only first and last few characters.

    Args:
        value: Value to mask
        visible_chars: Number of characters to show at start/end

    Returns:
        Masked value (e.g., "tvly-****-abcd")

    Example:
        >>> mask_sensitive_value("tvly-1234567890abcdef")
        "tvly-****-cdef"
    """
    if not value or len(value) <= visible_chars * 2:
        return "****"

    start = value[:visible_chars]
    end = value[-visible_chars:]
    return f"{start}-****-{end}"


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted.

    Fernet tokens have specific format characteristics.

    Args:
        value: Value to check

    Returns:
        True if value appears to be Fernet-encrypted
    """
    if not value:
        return False

    # Fernet tokens are base64-encoded and start with "gAAAAA"
    # They're typically 100+ characters long
    try:
        return (
            len(value) > 80 and
            value.startswith("gAAAAA") and
            all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=" for c in value)
        )
    except Exception:
        return False


def get_decrypted_config_value(
    config: dict,
    key: str,
    fallback_env_var: Optional[str] = None
) -> Optional[str]:
    """
    Get a configuration value, decrypting if necessary.

    Priority:
    1. Encrypted value in config
    2. Plain value in config
    3. Environment variable (if fallback_env_var provided)

    Args:
        config: Configuration dictionary (e.g., tool.config)
        key: Configuration key to retrieve
        fallback_env_var: Optional environment variable name to check

    Returns:
        Decrypted value or None if not found

    Example:
        >>> config = {"api_key": "gAAAAABf..."}
        >>> get_decrypted_config_value(config, "api_key", "TAVILY_API_KEY")
        "tvly-1234567890abcdef"
    """
    # Check config first
    value = config.get(key)

    if value:
        # Decrypt if encrypted
        if is_encrypted(value):
            try:
                return decrypt_value(value)
            except Exception as e:
                logger.error(f"Failed to decrypt config value for {key}: {e}")
                return None
        return value

    # Fall back to environment variable
    if fallback_env_var:
        env_value = getattr(settings, fallback_env_var.lower(), None)
        if env_value:
            logger.debug(f"Using environment variable {fallback_env_var} for {key}")
            return env_value

    return None
