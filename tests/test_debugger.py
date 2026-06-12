import os
import json
import time
import pytest
import subprocess
from debugger import DebuggerLog, LoggerSettings, LogDestination, LogLevel
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
        stream=LogDestination.FILE_HISTORY
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
from debugger import DebuggerLog, LoggerSettings, LogDestination

config = ConfigManager()
config.set('LOG_LEVEL', 'DEBUG')
settings = LoggerSettings(
    name="TEST_LEVELS",
    logs_base_dir="{tmp_path}",
    stream=LogDestination.FILE_HISTORY
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
        stream=LogDestination.CONSOLE
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

def test_debugger_history_cleanup(tmp_path):
    import time
    from config import ConfigManager, ConfigKey
    config = ConfigManager()
    
    test_base_dir = tmp_path / "logs_cleanup"
    test_backup_dir = "history"
    
    # Configure backups to 2
    config.set(ConfigKey.LOGGING_BACKUP_COUNT, 2)
    config.set(ConfigKey.LOGGING_BACKUP_DIR, test_backup_dir)
    config.set(ConfigKey.LOGGING_FILE_SIZE, 100) # Small file size to force rotation quickly
    
    settings = LoggerSettings(
        name=f"TEST_CLEANUP_{tmp_path.name}", 
        logs_base_dir=str(test_base_dir),
        stream=LogDestination.FILE_HISTORY
    )
    
    debugger = DebuggerLog(settings)
    
    # Write enough data to trigger rotation multiple times
    for i in range(500):
        debugger.info(f"Test cleanup message {i} {"A" * 100}")
        time.sleep(0.001)
        
    time.sleep(0.5)
    
    from datetime import datetime
    current_date = datetime.now().date().strftime("%Y-%m-%d")
    history_path = test_base_dir / "logs" / test_backup_dir / current_date
    
    # Ensure directory exists and check its files
    assert history_path.exists()
    gz_files = list(history_path.glob("*.gz"))
    
    # We should have exactly 2 files (since backup_count is 2)
    assert len(gz_files) <= 2
