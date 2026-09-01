import hmac
import hashlib
import secrets
from typing import Any

from loggerbuf.config import ConfigManager, ConfigKey, PiiMethod

# Session salt generated once per process lifecycle to ensure 
# deterministic hashing for the same session if PII_HASH_SALT is not provided.
_SESSION_SALT = secrets.token_hex(16)

def apply_pii_mask(value: Any) -> str:
    """
    Applies the configured PII mask to the given value.
    If PII masking is disabled, returns the string representation of the original value.
    """
    config = ConfigManager()
    
    is_enabled = config.get(ConfigKey.PII_MASK_ENABLED, True)
    if not is_enabled:
        return str(value)

    method = config.get(ConfigKey.PII_MASK_METHOD, PiiMethod.REDACTED)
    
    if method == PiiMethod.REDACTED:
        return "[REDACTED]"
        
    elif method == PiiMethod.HASH:
        # Get the independent salt or fallback to the session salt
        salt = config.get(ConfigKey.PII_HASH_SALT)
        if not salt:
            salt = _SESSION_SALT
            
        value_bytes = str(value).encode("utf-8")
        salt_bytes = salt.encode("utf-8")
        
        # Create a deterministic HMAC SHA-256 hash
        hashed = hmac.new(salt_bytes, value_bytes, hashlib.sha256).hexdigest()
        
        # Return truncated hash for logging brevity
        return f"[HASH:{hashed[:10]}]"
        
    return str(value)

def pii_mask(value: Any) -> str:
    """
    Public helper function to manually mask sensitive information in free-text logs.
    Example:
        logger.info(f"User {pii_mask(email)} connected")
    """
    return apply_pii_mask(value)
