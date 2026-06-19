import json
import logging
import unittest
from unittest.mock import MagicMock

from loggerbuf.debugger import JsonFormatter

class TestJsonFormatter(unittest.TestCase):
    def test_json_formatter_output(self):
        formatter = JsonFormatter()
        
        # Create a mock log record
        record = logging.LogRecord(
            name="TEST_LOGGER",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg="This is a test message",
            args=(),
            exc_info=None
        )
        record.caller_class = "TestClass"
        record.funcName = "test_func"
        
        # Format the record
        output = formatter.format(record)
        
        # Verify output is valid JSON
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            self.fail("Output is not valid JSON")
            
        # Verify fields
        self.assertEqual(parsed["logger"], "TEST_LOGGER")
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["file"], "test_file.py")
        self.assertEqual(parsed["class"], "TestClass")
        self.assertEqual(parsed["function"], "test_func")
        self.assertEqual(parsed["line"], 42)
        self.assertEqual(parsed["message"], "This is a test message")
        self.assertIn("timestamp", parsed)

    def test_json_formatter_missing_attributes(self):
        formatter = JsonFormatter()
        
        # Record missing caller_class
        record = logging.LogRecord(
            name="TEST_LOGGER",
            level=logging.DEBUG,
            pathname="test_file.py",
            lineno=10,
            msg="Another test",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        # Should fallback to default 'None' for class
        self.assertEqual(parsed["class"], "None")

if __name__ == "__main__":
    unittest.main()
