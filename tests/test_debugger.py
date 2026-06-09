import os
import re
import time
import pytest
from debugger import DebuggerLog, LoggerSettings, StreamLevel, LogLevel

# Strict Regex to validate the output log format
LOG_REGEX = re.compile(
    r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\] >>\w+<< \([\w.]+::\w+::\w+->\d+\) - \*\w+\* - message::>.*$"
)

class DummyCaller:
    def execute_log(self, logger):
        logger.info("This is a strict format test")

def test_debugger_log_format_and_file_creation(tmp_path):
    settings = LoggerSettings(
        name="TEST_APP",
        logs_base_dir=str(tmp_path),
        stream=StreamLevel.ONLY_FILE
    )
    logger = DebuggerLog(settings)
    
    caller = DummyCaller()
    caller.execute_log(logger)
    
    # Wait briefly for the daemon thread to write to disk
    time.sleep(0.1)
    
    log_dir = tmp_path / "logs"
    assert log_dir.exists()
    
    # Find the main log file
    files = list(log_dir.glob("logs_*.log"))
    assert len(files) == 1
    
    content = files[0].read_text().strip()
    assert content != ""
    
    lines = content.split('\n')
    assert len(lines) == 1
    line = lines[0]
    
    # Regex validation
    assert LOG_REGEX.match(line) is not None, f"Log line does not match strict format: {line}"
    assert "This is a strict format test" in line
    assert "DummyCaller" in line
    assert "execute_log" in line

def test_debugger_log_levels(tmp_path):
    settings = LoggerSettings(
        name="TEST_LEVELS",
        logs_base_dir=str(tmp_path),
        stream=StreamLevel.ONLY_FILE
    )
    logger = DebuggerLog(settings)
    
    # Default level is DEBUG for QueueHandler, but handlers dictate physical files
    logger.debug("Debug msg")
    logger.info("Info msg")
    logger.warning("Warn msg")
    logger.error("Error msg")
    logger.critical("Crit msg")
    
    time.sleep(0.1)
    
    main_files = list((tmp_path / "logs").glob("logs_TEST_LEVELS.log"))
    debug_files = list((tmp_path / "logs").glob("debug_logs_TEST_LEVELS.log"))
    
    assert len(main_files) == 1
    assert len(debug_files) == 1
    
    main_content = main_files[0].read_text()
    debug_content = debug_files[0].read_text()
    
    assert "Info msg" in main_content
    assert "Debug msg" not in main_content # DEBUG should not be in main log
    
    assert "Debug msg" in debug_content
    assert "Crit msg" in debug_content

def test_debugger_console_filters(capsys):
    settings = LoggerSettings(
        name="TEST_CONSOLE",
        stream=StreamLevel.ONLY_CONSOLE
    )
    logger = DebuggerLog(settings)
    
    logger.info("Should see this console message")
    time.sleep(0.1)
    
    captured = capsys.readouterr()
    assert "Should see this console message" in captured.err
    
    logger.disable_console()
    logger.info("Should NOT see this console message")
    time.sleep(0.1)
    
    captured2 = capsys.readouterr()
    assert "Should NOT see this console message" not in captured2.err
