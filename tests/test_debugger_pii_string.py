import unittest
from unittest.mock import patch
from loggerbuf.debugger import DebuggerLog
from loggerbuf.config import ConfigManager, ConfigKey, PiiMethod
import json
import logging

class TestDebuggerPIIString(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.config.set(ConfigKey.PII_MASK_ENABLED, True)
        self.config.set(ConfigKey.PII_MASK_METHOD, PiiMethod.REDACTED)
        self.config.set(ConfigKey.PII_PROTECTED_FIELDS, "password,secret")

    def test_debugger_pii_kwargs_string(self):
        log = DebuggerLog()
        
        with patch.object(logging.Logger, "log") as mock_log:
            log.info({"user": "cal", "password": "super_secret_password", "nested": {"secret": "hidden"}})
            
            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            message = args[1]
            
            parsed = json.loads(message)
            self.assertEqual(parsed["user"], "cal")
            self.assertEqual(parsed["password"], "[REDACTED]")
            self.assertEqual(parsed["nested"]["secret"], "[REDACTED]")

if __name__ == "__main__":
    unittest.main()
