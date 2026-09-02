import hmac
import hashlib
import secrets
from typing import Any

from loggerbuf.config import ConfigManager, ConfigKey, PiiMethod

_SESSION_SALT = secrets.token_hex(16)

def apply_pii_mask(value: Any, force: bool = False) -> str:
    config = ConfigManager()
    
    is_enabled = config.get(ConfigKey.PII_MASK_ENABLED, True)
    if not is_enabled and not force:
        return str(value)

    method = config.get(ConfigKey.PII_MASK_METHOD, PiiMethod.REDACTED)
    
    if method == PiiMethod.REDACTED:
        return "[REDACTED]"
        
    elif method == PiiMethod.HASH:
        salt = config.get(ConfigKey.PII_HASH_SALT)
        if not salt:
            salt = _SESSION_SALT
            
        value_bytes = str(value).encode("utf-8")
        salt_bytes = salt.encode("utf-8")
        
        hashed = hmac.new(salt_bytes, value_bytes, hashlib.sha256).hexdigest()
        return f"[HASH:{hashed[:10]}]"
        
    return str(value)

def pii_mask(value: Any, force: bool = False) -> str:
    return apply_pii_mask(value, force=force)

def mask_dict(data: Any, protected_fields: list) -> Any:
    """Recursively mask dictionary values if their key is in protected_fields."""
    if not protected_fields:
        return data
        
    if isinstance(data, dict):
        masked_data = {}
        for k, v in data.items():
            if str(k).lower() in [f.lower() for f in protected_fields]:
                masked_data[k] = apply_pii_mask(v)
            else:
                masked_data[k] = mask_dict(v, protected_fields)
        return masked_data
    elif isinstance(data, list):
        return [mask_dict(item, protected_fields) for item in data]
    elif isinstance(data, tuple):
        return tuple(mask_dict(item, protected_fields) for item in data)
    return data
