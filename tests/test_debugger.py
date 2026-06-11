import os
import json
import time
import pytest
import subprocess
from debugger import DebuggerLog, LoggerSettings, StreamLevel, LogLevel
from config import ConfigManager

class DummyCaller:
    def execute_log(self, logger):
        logger.info("This is a strict format test")

def test_debugger_log_format_and_file_creation(tmp_path):
    config = ConfigManager()
    config.set('LOG_LEVEL', 'DEBUG')
    settings = LoggerSettings(
        name="TEST_APP",
        logs_base_dir=str(tmp_path),
        stream=StreamLevel.ONLY_FILE
    )
    logger = DebuggerLog(settings)
    
    caller = DummyCaller()
    caller.execute_log(logger)
    
    # Wait briefly for the daemon thread to write to disk
    time.sleep(0.5)
    
    log_dir = tmp_path / "logs"
    assert log_dir.exists()
    
    files = list(log_dir.glob("debug_logs_*.log"))
    assert len(files) == 1
    
    content = files[0].read_text().strip()
    assert content != ""
    
    lines = content.split('\n')
    assert len(lines) == 1
    line = lines[0]
    
    log_obj = json.loads(line)
    assert log_obj["logger"] == "TEST_APP"
    assert log_obj["level"] == "INFO"
    assert "This is a strict format test" in log_obj["message"]
    assert log_obj["class"] == "DummyCaller"
    assert log_obj["function"] == "execute_log"

def test_debugger_log_levels(tmp_path):
    script = tmp_path / "run_levels.py"
    script.write_text(f"""
import time
from config import ConfigManager
from debugger import DebuggerLog, LoggerSettings, StreamLevel

config = ConfigManager()
config.set('LOG_LEVEL', 'DEBUG')
settings = LoggerSettings(
    name="TEST_LEVELS",
    logs_base_dir="{tmp_path}",
    stream=StreamLevel.ONLY_FILE
)
logger = DebuggerLog(settings)
logger.debug("Debug msg")
logger.info("Info msg")
logger.warning("Warn msg")
logger.error("Error msg")
logger.critical("Crit msg")
time.sleep(0.5)
""")
    subprocess.run(["python3", str(script)], env={"PYTHONPATH": os.getcwd()}, check=True)
    
    debug_files = list((tmp_path / "logs").glob("debug_logs_TEST_LEVELS.log"))
    assert len(debug_files) == 1
    
    debug_content = debug_files[0].read_text()
    
    assert "Info msg" in debug_content
    assert "Debug msg" in debug_content
    assert "Crit msg" in debug_content
    assert "Warn msg" in debug_content
    assert "Error msg" in debug_content

def test_debugger_console_filters(capsys):
    settings = LoggerSettings(
        name="TEST_CONSOLE",
        stream=StreamLevel.ONLY_CONSOLE
    )
    logger = DebuggerLog(settings)
    
    logger.info("Should see this console message")
    time.sleep(0.5)
    
    captured = capsys.readouterr()
    assert "Should see this console message" in captured.err
    
    logger.disable_console()
    logger.info("Should NOT see this console message")
    time.sleep(0.5)
    
    captured2 = capsys.readouterr()
    assert "Should NOT see this console message" not in captured2.err
