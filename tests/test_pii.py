import unittest
import pytest
from unittest.mock import patch
from loggerbuf.pii import apply_pii_mask, pii_mask
from loggerbuf.config import ConfigManager, ConfigKey, PiiMethod

class TestPiiMasking(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        # Reset config to defaults before each test
        self.config.set(ConfigKey.PII_MASK_ENABLED, True)
        self.config.set(ConfigKey.PII_MASK_METHOD, PiiMethod.REDACTED)
        self.config.set(ConfigKey.PII_HASH_SALT, None)

    def test_pii_mask_disabled(self):
        self.config.set(ConfigKey.PII_MASK_ENABLED, False)
        self.assertEqual(apply_pii_mask("sensitive_data"), "sensitive_data")
        self.assertEqual(pii_mask("sensitive_data"), "sensitive_data")

    def test_pii_mask_redacted(self):
        self.config.set(ConfigKey.PII_MASK_METHOD, PiiMethod.REDACTED)
        self.assertEqual(apply_pii_mask("sensitive_data"), "[REDACTED]")

    def test_pii_mask_hash_with_salt(self):
        self.config.set(ConfigKey.PII_MASK_METHOD, PiiMethod.HASH)
        self.config.set(ConfigKey.PII_HASH_SALT, "my_custom_salt")
        
        result1 = apply_pii_mask("cal@example.com")
        result2 = apply_pii_mask("cal@example.com")
        
        # Hashes should be identical for the same input
        self.assertEqual(result1, result2)
        self.assertTrue(result1.startswith("[HASH:"))
        
        # Different input should have different hash
        result3 = apply_pii_mask("other@example.com")
        self.assertNotEqual(result1, result3)

    def test_pii_mask_hash_session_salt(self):
        self.config.set(ConfigKey.PII_MASK_METHOD, PiiMethod.HASH)
        self.config.set(ConfigKey.PII_HASH_SALT, None)
        
        result1 = apply_pii_mask("test@example.com")
        result2 = apply_pii_mask("test@example.com")
        
        # Should still be deterministic within the same session
        self.assertEqual(result1, result2)
        self.assertTrue(result1.startswith("[HASH:"))

if __name__ == "__main__":
    unittest.main()
