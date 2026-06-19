from .debugger import DebuggerLog, LoggerSettings, LogDestination, LogLevel
from .telemetry import TelemetryLog, EventSettings
from .cli.handlers.decode import decode_file

def create_debugger(name="MAIN", stream=LogDestination.CONSOLE_AND_FILE_HISTORY, logs_base_dir="."):
    """
    Helper function to get or create an operational Debugger instance.
    
    Parameters
    ----------
    name : str
        Name of the debugger channel.
    stream : LogDestination
        Where to send logs (ONLY_CONSOLE, ONLY_FILE, CONSOLE_AND_FILE_HISTORY).
    logs_base_dir : str
        Base directory to store operational logs.
    """
    settings = LoggerSettings(name=name, logs_base_dir=logs_base_dir, stream=stream)
    return DebuggerLog(settings)

def create_telemetry(name="MAIN", logs_base_dir="."):
    """
    Helper function to get or create a structured Telemetry instance.
    
    Parameters
    ----------
    name : str
        Name of the telemetry channel.
    logs_base_dir : str
        Base directory to store binary telemetry files.
    """
    settings = EventSettings(name=name, logs_base_dir=logs_base_dir)
    return TelemetryLog(settings)
