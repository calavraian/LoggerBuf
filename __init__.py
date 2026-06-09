from .debugger import DebuggerLog, LoggerSettings, StreamLevel, LogLevel
from .telemetry import TelemetryLog, EventSettings
from .decoder import LoggerBufDecoder

def get_debugger(name="MAIN", stream=StreamLevel.FILE_CONSOLE, logs_base_dir="."):
    """
    Helper function to get or create an operational Debugger instance.
    
    Parameters
    ----------
    name : str
        Name of the debugger channel.
    stream : StreamLevel
        Where to send logs (ONLY_CONSOLE, ONLY_FILE, FILE_CONSOLE).
    logs_base_dir : str
        Base directory to store operational logs.
    """
    settings = LoggerSettings(name=name, logs_base_dir=logs_base_dir, stream=stream)
    return DebuggerLog(settings)

def get_telemetry(logs_base_dir="."):
    """
    Helper function to get or create a structured Telemetry instance.
    
    Parameters
    ----------
    logs_base_dir : str
        Base directory to store binary telemetry files.
    """
    settings = EventSettings(logs_base_dir=logs_base_dir)
    return TelemetryLog(settings)
