import os
import json
import tempfile
import unittest
import gzip
from io import StringIO
import sys

from loggerbuf.cli.handlers.decode import decode_debug_file, run_decode_debug

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

    def test_run_decode_debug_format_jsonl(self):
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        try:
            run_decode_debug(self.test_log_file, format_style="jsonl")
        finally:
            sys.stdout = old_stdout
            
        output = captured.getvalue()
        # Should be exact json lines
        self.assertIn('"message": "First message"', output)
        self.assertTrue(output.startswith('{"timestamp"'))
        
    def test_run_decode_debug_format_pretty(self):
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        try:
            run_decode_debug(self.test_log_file, format_style="pretty")
        finally:
            sys.stdout = old_stdout
            
        output = captured.getvalue()
        # Should have pretty indentation
        self.assertIn('  "message": "First message"', output)
        self.assertIn('{\n  "timestamp"', output)
        
    def test_run_decode_debug_output_file(self):
        output_file = os.path.join(self.temp_dir.name, "output.txt")
        run_decode_debug(self.test_log_file, output_file=output_file)
        
        self.assertTrue(os.path.exists(output_file))
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("First message", content)
            self.assertIn("Failed to connect", content)

    def test_run_decode_debug_filtered_warning(self):
        # Create a log file with a missing required field (e.g., 'file')
        filtered_log_file = os.path.join(self.temp_dir.name, "debug_filtered.log")
        filtered_entries = [
            {"timestamp": "2026-06-11 10:00:00,000", "logger": "TEST_APP", "level": "INFO", "class": "None", "function": "main", "line": 10, "message": "Msg 1"},
            {"timestamp": "2026-06-11 10:00:01,000", "logger": "TEST_APP", "level": "ERROR", "file": "test.py", "class": "MyClass", "function": "do_work", "line": 20, "message": "Msg 2"}
        ]
        
        with open(filtered_log_file, "w", encoding="utf-8") as f:
            for entry in filtered_entries:
                f.write(json.dumps(entry) + "\n")
                
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = captured_stdout = StringIO()
        sys.stderr = captured_stderr = StringIO()
        
        try:
            run_decode_debug(filtered_log_file)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
        out = captured_stdout.getvalue()
        err = captured_stderr.getvalue()
        
        # Check that warning is printed to stderr exactly once
        self.assertIn("Lines with filtered metadata detected in this file", err)
        self.assertEqual(err.count("Lines with filtered metadata detected in this file"), 1)
        
        # Check that the first line (missing 'file') has the *F* prefix
        self.assertIn("\033[95m*F*\033[0m [2026-06-11 10:00:00,000]", out)
        # Check that the second line (complete) DOES NOT have the *F* prefix
        self.assertIn("[2026-06-11 10:00:01,000]", out)
        self.assertNotIn("\033[95m*F*\033[0m [2026-06-11 10:00:01,000]", out)

if __name__ == '__main__':
    unittest.main()
