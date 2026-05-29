from .debulogger import Logger, LoggerSettings, StreamLevel, LogLevel
from .eventlogger import EventLogger, EventSettings
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
    return Logger(settings)

def get_telemetry(logs_base_dir="."):
    """
    Helper function to get or create a structured Telemetry (EventLogger) instance.
    
    Parameters
    ----------
    logs_base_dir : str
        Base directory to store binary telemetry files.
    """
    settings = EventSettings(logs_base_dir=logs_base_dir)
    return EventLogger(settings)
