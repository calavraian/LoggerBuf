import os
import json
import tempfile
import unittest
import gzip
from io import StringIO
import sys

from cli.handlers.decode import decode_debug_file, run_decode_debug

class TestDecodeDebug(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory and files for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_log_file = os.path.join(self.temp_dir.name, "debug_TEST.log")
        self.test_gz_file = os.path.join(self.temp_dir.name, "debug_TEST.log.1.gz")
        
        self.log_entries = [
            {"timestamp": "2026-06-11 10:00:00,000", "logger": "TEST_APP", "level": "INFO", "file": "test.py", "class": "None", "function": "main", "line": 10, "message": "First message"},
            {"timestamp": "2026-06-11 10:00:01,000", "logger": "TEST_APP", "level": "ERROR", "file": "test.py", "class": "MyClass", "function": "do_work", "line": 20, "message": "Failed to connect"}
        ]
        
        # Write plain JSON lines
        with open(self.test_log_file, "w", encoding="utf-8") as f:
            for entry in self.log_entries:
                f.write(json.dumps(entry) + "\n")
                
        # Write gzip JSON lines
        with gzip.open(self.test_gz_file, "wt", encoding="utf-8") as f:
            for entry in self.log_entries:
                f.write(json.dumps(entry) + "\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_decode_debug_file_plain(self):
        generator = decode_debug_file(self.test_log_file)
        results = list(generator)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["message"], "First message")

    def test_decode_debug_file_gzip(self):
        generator = decode_debug_file(self.test_gz_file)
        results = list(generator)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1]["message"], "Failed to connect")

    def test_run_decode_debug_output(self):
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        
        try:
            run_decode_debug(self.test_log_file)
        finally:
            sys.stdout = old_stdout
            
        output = captured.getvalue()
        
        # Verify format matches expected pretty output
        self.assertIn("[2026-06-11 10:00:00,000] >>TEST_APP<< (test.py::None::main->10) - *INFO* - message::>First message", output)
        self.assertIn("[2026-06-11 10:00:01,000] >>TEST_APP<< (test.py::MyClass::do_work->20) - *ERROR* - message::>Failed to connect", output)

    def test_run_decode_debug_grep(self):
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        
        try:
            run_decode_debug(self.test_log_file, grep_keyword="failed")
        finally:
            sys.stdout = old_stdout
            
        output = captured.getvalue()
        
        # Should only contain the second message
        self.assertNotIn("First message", output)
        self.assertIn("Failed to connect", output)

    def test_run_decode_debug_head(self):
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        
        try:
            run_decode_debug(self.test_log_file, head=1)
        finally:
            sys.stdout = old_stdout
            
        output = captured.getvalue()
        self.assertIn("First message", output)
        self.assertNotIn("Failed to connect", output)

    def test_run_decode_debug_tail(self):
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        
        try:
            run_decode_debug(self.test_log_file, tail=1)
        finally:
            sys.stdout = old_stdout
            
        output = captured.getvalue()
        self.assertNotIn("First message", output)
        self.assertIn("Failed to connect", output)

if __name__ == "__main__":
    unittest.main()
