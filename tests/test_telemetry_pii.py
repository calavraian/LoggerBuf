import unittest
from unittest.mock import patch
from loggerbuf.telemetry import TelemetryLog
from loggerbuf.config import ConfigManager, ConfigKey, PiiMethod
from loggerbuf import schema_loader

registry_pb2 = schema_loader.get_registry_pb2()

class TestTelemetryPII(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.config.set(ConfigKey.PII_MASK_ENABLED, True)
        self.config.set(ConfigKey.PII_MASK_METHOD, PiiMethod.REDACTED)
        self.config.set(ConfigKey.PII_PROTECTED_FIELDS, ["general_note"])

    def test_telemetry_pii_fields(self):
        log = TelemetryLog()
        
        with patch.object(log._TelemetryLog__event_writer, "write_event") as mock_write:
            log.log_event(
                event_type=registry_pb2.EventType.EVENT_GENERIC,
                general_note="My secret note"
            )
            
            mock_write.assert_called_once()
            event = mock_write.call_args[0][0]
            
            self.assertEqual(event.general_note, "[REDACTED]")

if __name__ == "__main__":
    unittest.main()
