import datetime
import gzip
import json
import logging
import os
import queue
import sys
import threading
import time
from .config import ConfigManager, CONFIG_FILE, QueueStrategy, ConfigKey, LogMetadata

from enum import Enum
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener

class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class LogDestination(Enum):
    CONSOLE = 1
    FILE_LIVE = 2
    FILE_HISTORY = 3
    CONSOLE_AND_FILE_LIVE = 4
    CONSOLE_AND_FILE_HISTORY = 5

class RolloverType(Enum):
    NONE = 0
    TIME = 1
    SIZE = 2

from .config import QueueStrategy

class LoggerBufQueueHandler(QueueHandler):
    def __init__(self, queue_obj, strategy: QueueStrategy = QueueStrategy.LOSSY):
        super().__init__(queue_obj)
        self.strategy = strategy

    def enqueue(self, record):
        if self.strategy == QueueStrategy.LOSSY:
            try:
                self.queue.put_nowait(record)
            except queue.Full:
                # Silently drop under high load to protect caller thread performance
                pass
        else:
            # "lossless" -> block client thread until space is available
            self.queue.put(record)


class ConsoleFilter(logging.Filter):
    def __init__(self, is_enabled: bool):
        super().__init__()
        self.is_enabled = is_enabled
        self.allowed_classes = None
        self.allowed_levels = None

    def filter(self, record):
        if not self.is_enabled:
            return False
            
        if self.allowed_classes is not None:
            caller_class = getattr(record, 'caller_class', None)
            if caller_class not in self.allowed_classes:
                return False
                
        if self.allowed_levels is not None:
            if record.levelno not in self.allowed_levels:
                return False
                
        return True



class JsonFormatter(logging.Formatter):
    def __init__(self, metadata_fields=None):
        super().__init__()
        if metadata_fields is None:
            self.metadata_fields = [e.value for e in LogMetadata]
        else:
            self.metadata_fields = metadata_fields

    def format(self, record):
        log_obj = {}
        if LogMetadata.TIMESTAMP.value in self.metadata_fields:
            log_obj["timestamp"] = self.formatTime(record, self.datefmt)
        if LogMetadata.LOGGER.value in self.metadata_fields:
            log_obj["logger"] = record.name
        if LogMetadata.LEVEL.value in self.metadata_fields:
            log_obj["level"] = record.levelname
        if LogMetadata.FILE.value in self.metadata_fields:
            log_obj["file"] = getattr(record, "filename", "Unknown")
        if LogMetadata.CLASS.value in self.metadata_fields:
            log_obj["class"] = getattr(record, "caller_class", "None")
        if LogMetadata.FUNCTION.value in self.metadata_fields:
            log_obj["function"] = getattr(record, "funcName", "Unknown")
        if LogMetadata.LINE.value in self.metadata_fields:
            log_obj["line"] = getattr(record, "lineno", 0)
        
        log_obj["message"] = record.getMessage()
        return json.dumps(log_obj, ensure_ascii=False)


class LoggingUtils():
    @staticmethod
    def get_date_last_record(file_name):
        if not os.path.exists(file_name) or os.path.getsize(file_name) == 0:
            return None
        
        last_line = ""
        try:
            with open(file_name, 'rb') as f:
                # Seek to end of file
                f.seek(0, os.SEEK_END)
                position = f.tell()
                
                # Seek back starting with 4KB, exponentially backoff up to the entire file
                seek_back = min(4096, position)
                while True:
                    f.seek(position - seek_back, os.SEEK_SET)
                    chunk = f.read(seek_back)
                    
                    # Split lines by binary newline
                    lines = chunk.split(b'\n')
                    # Find the last non-empty line starting with '[' (old text log) or '{' (json log)
                    for line in reversed(lines):
                        decoded = line.strip().decode('utf-8', errors='ignore')
                        if decoded and (decoded.startswith("[") or decoded.startswith("{")):
                            last_line = decoded
                            break
                            
                    if last_line:
                        break
                        
                    if seek_back == position:
                        # Reached the beginning of the file and still found nothing
                        break
                        
                    # Exponentially expand the read buffer backwards
                    seek_back = min(seek_back * 2, position)
        except Exception as e:
            print(f"Error reading last record of {file_name}: {e}")
            return None

        if not last_line:
            return None
            
        try:
            if last_line.startswith("{"):
                data = json.loads(last_line)
                date_str = data.get("timestamp", "")[:10]
            else:
                date_str = last_line[1:11]
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return None



class LoggerSettings:
    def __init__(self,
            name: str = None,
            logs_base_dir: str = ".", 
            backup_dir: str = None,
            file_size: int = None,
            stream: LogDestination = None):
        """
        Configuration for the logger.
        
        Args:
            name (str, optional): Name of the logger. Defaults to None (will use default config).
            logs_base_dir (str, optional): The base directory for all logs. Defaults to None (will use default config).
            backup_dir (str, optional): The directory for rotated logs. Defaults to None (will use default config).
            file_size (int, optional): The maximum file size in bytes before rotation. Defaults to None.
            stream (LogDestination, optional): Logging destination. Defaults to None (will fetch from config, fallback to CONSOLE).
        """
        config = ConfigManager()
        self.__name = name if name is not None else config.get(ConfigKey.LOGGING_LOGGER_NAME)
        self.__logs_base_dir = logs_base_dir 
        self.__backup_dir = backup_dir if backup_dir is not None else config.get(ConfigKey.LOGGING_BACKUP_DIR)
        self.__file_size = file_size if file_size is not None else config.get(ConfigKey.LOGGING_FILE_SIZE)
        
        if stream is not None:
            self.__stream = stream
        else:
            dest_str = config.get(ConfigKey.LOGGING_DESTINATION)
            try:
                self.__stream = LogDestination[str(dest_str).upper()]
            except (KeyError, AttributeError):
                self.__stream = LogDestination.CONSOLE
    
    def get_name(self):
        """
        Gets the name of the logger.

        Returns
        -------
        str
            The name of the logger.
        """
        return self.__name
    
    def get_logs_base_dir(self):        
        """
        Gets the base directory for logs.

        Returns
        -------
        str
            The base directory for logs.
        """
        return self.__logs_base_dir
    
    def get_backup_dir(self):
        """
        Gets the directory for backup logs.

        Returns
        -------
        str
            The directory for backup logs.
        """
        return self.__backup_dir
    
    def get_file_size(self):
        """
        Gets the maximum size of each log file.

        Returns
        -------
        int
            The maximum size of each log file in bytes.
        """

        return self.__file_size
    
    def get_stream(self):
        """
        Gets the type of stream for the logger.

        Returns
        -------
        LogDestination
            The stream type for the logger.
        """
        return self.__stream

class DebuggerLog:
    __loggers = {}
    __listeners = {}
    __lock = threading.RLock()

    def __init__(self, settings: LoggerSettings = None):
        if not settings:
            settings = LoggerSettings()
        
        with DebuggerLog.__lock:
            name = settings.get_name()
            if name not in DebuggerLog.__loggers:
                self.__settings = settings
                
                config_manager = ConfigManager()
                
                # Retrieve configuration with safe defaults
                queue_max_size = config_manager.get(ConfigKey.LOGGING_QUEUE_MAX_SIZE)
                queue_strategy_val = config_manager.get(ConfigKey.LOGGING_QUEUE_STRATEGY)
                queue_strategy = QueueStrategy.LOSSY
                if queue_strategy_val == "LOSSLESS":
                    queue_strategy = QueueStrategy.LOSSLESS
                elif queue_strategy_val == "LOSSY":
                    queue_strategy = QueueStrategy.LOSSY
                
                full_path_logs = self.__full_path_logs()
                debug_log_file = os.path.join(full_path_logs, f"{config_manager.get(ConfigKey.LOGGING_DEBUG_FILE_NAME)}_{name}.log")

                # Consolidated to single file
                log_level_str = config_manager.get(ConfigKey.LOG_LEVEL, 'DEBUG')
                print("DEBUG: log_level_str in init is", log_level_str)
                initial_level = getattr(logging, log_level_str.upper(), logging.DEBUG)
                
                debug_handler = self.__create_size_time_rotating_handler(filename=debug_log_file, logLevel=initial_level)
                stream_handler = self.__create_stream_handler()

                # Initialize console filter based on settings
                dest = self.__settings.get_stream()
                console_enabled = dest in (LogDestination.CONSOLE, LogDestination.CONSOLE_AND_FILE_LIVE, LogDestination.CONSOLE_AND_FILE_HISTORY)
                console_filter = ConsoleFilter(is_enabled=console_enabled)
                stream_handler.addFilter(console_filter)
                
                dest_handlers = []
                if dest in (LogDestination.FILE_LIVE, LogDestination.FILE_HISTORY, LogDestination.CONSOLE_AND_FILE_LIVE, LogDestination.CONSOLE_AND_FILE_HISTORY):
                    dest_handlers.append(debug_handler)

                # Always add stream_handler, output is controlled by ConsoleFilter
                dest_handlers.append(stream_handler)

                # Initialize Queue
                print("queue_max_size is", queue_max_size)

                log_queue = queue.Queue(maxsize=queue_max_size)
                
                # Custom Queue Handler
                queue_handler = LoggerBufQueueHandler(log_queue, strategy=queue_strategy)
                queue_handler.setLevel(logging.DEBUG)
                
                # Native Logger Setup
                logger = logging.getLogger(name)
                logger.setLevel(logging.DEBUG)
                logger.propagate = False
                logger.addHandler(queue_handler)

                # Queue Listener to dispatch logs to real handlers on a daemon worker thread
                listener = QueueListener(log_queue, *dest_handlers, respect_handler_level=True)
                listener.start()

                DebuggerLog.__loggers[name] = (self.__settings, logger, console_filter)
                DebuggerLog.__listeners[name] = listener

                # Apply initial console settings IMMEDIATELY before global watcher could trigger
                self._on_console_config_change(None)

                # Subscribe to global ConfigWatcher for hot-reloading LOG_LEVEL
                config_manager.subscribe(ConfigKey.LOG_LEVEL, self._on_log_level_change)
                config_manager.subscribe(ConfigKey.LOGGING_CONSOLE_ENABLED, self._on_console_config_change)
                config_manager.subscribe(ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, self._on_console_config_change)
                config_manager.subscribe(ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, self._on_console_config_change)
                config_manager.subscribe(ConfigKey.LOGGING_METADATA, self._on_metadata_change)
                config_manager.subscribe(ConfigKey.LOGGING_CONSOLE_METADATA, self._on_console_metadata_change)
            else:
                self.__settings = DebuggerLog.__loggers[name][0]


    def __get_log_format(self, fields):
        parts = []
        if LogMetadata.TIMESTAMP.value in fields:
            parts.append('[{asctime}]')
        
        if LogMetadata.LOGGER.value in fields:
            parts.append('>>{name}<<')
            
        loc_parts = []
        if LogMetadata.FILE.value in fields:
            loc_parts.append('{filename}')
        if LogMetadata.CLASS.value in fields:
            loc_parts.append('{caller_class}')
        if LogMetadata.FUNCTION.value in fields:
            loc_parts.append('{funcName}')
        if loc_parts:
            loc_str = "::".join(loc_parts)
            if LogMetadata.LINE.value in fields:
                loc_str += "->{lineno}"
            parts.append(f"({loc_str})")
            
        if LogMetadata.LEVEL.value in fields:
            parts.append('- *{levelname}* -')
            
        parts.append('message::>{message}')
        return " ".join(parts)

    def _on_console_config_change(self, _):
        config_manager = ConfigManager()
        enabled = config_manager.get(ConfigKey.LOGGING_CONSOLE_ENABLED, True)
        allowed_classes = config_manager.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, [])
        allowed_levels_str = config_manager.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, [])
        
        allowed_classes = None if not allowed_classes else allowed_classes
        allowed_levels = None
        if allowed_levels_str:
            allowed_levels = [getattr(logging, lvl.upper(), logging.DEBUG) for lvl in allowed_levels_str]

        if enabled:
            self.enable_console(allowed_classes, allowed_levels)
        else:
            self.disable_console()

    def _on_metadata_change(self, new_metadata):
        name = self.__settings.get_name()
        if name in DebuggerLog.__listeners:
            listener = DebuggerLog.__listeners[name]
            for handler in listener.handlers:
                is_json = isinstance(handler, SizedTimedRotatingFileHandler)
                if is_json:
                    self.__config_handler(handler, handler.level, rotator=is_json, is_json=is_json)

    def _on_console_metadata_change(self, new_metadata):
        name = self.__settings.get_name()
        if name in DebuggerLog.__listeners:
            listener = DebuggerLog.__listeners[name]
            for handler in listener.handlers:
                is_json = isinstance(handler, SizedTimedRotatingFileHandler)
                if not is_json:
                    self.__config_handler(handler, handler.level, rotator=is_json, is_json=is_json)

    def _on_log_level_change(self, new_level_str):
        """Called by ConfigManager when LOG_LEVEL changes."""
        new_level = getattr(logging, str(new_level_str).upper(), logging.DEBUG)
        
        # Update global logger level and file handler levels
        self.setLoggerToLevel(LogLevel(new_level))
        
        # Update the file handlers
        name = self.__settings.get_name()
        if name in DebuggerLog.__listeners:
            listener = DebuggerLog.__listeners[name]
            for handler in listener.handlers:
                if isinstance(handler, SizedTimedRotatingFileHandler):
                    handler.setLevel(new_level)

    def enable_console(self, allowed_classes: list = None, allowed_levels: list = None):
        """
        Dynamically enables the console output.
        Optionally filters by a list of class names or log levels.
        """
        name = self.__settings.get_name()
        if name in DebuggerLog.__loggers:
            console_filter = DebuggerLog.__loggers[name][2]
            with DebuggerLog.__lock:
                console_filter.allowed_classes = allowed_classes
                console_filter.allowed_levels = allowed_levels
                console_filter.is_enabled = True

    def stop_rotation_timer(self):
        """
        Stops the hourly timer for rotation (if applicable).
        """
        name = self.__settings.get_name()
        if name in DebuggerLog.__loggers:
            if hasattr(self, '_DebuggerLog__rotation_timer') and self.__rotation_timer:
                self.__rotation_timer.cancel()
                
    def shutdown(self):
        """
        Gracefully stops the queue listener and closes handlers.
        """
        name = self.__settings.get_name()
        if name in DebuggerLog.__listeners:
            listener = DebuggerLog.__listeners[name]
            listener.stop()
            del DebuggerLog.__listeners[name]
        
        self.stop_rotation_timer()
        
        if name in DebuggerLog.__loggers:
            del DebuggerLog.__loggers[name]

    def disable_console(self):
        """
        Dynamically disables the console output.
        """
        name = self.__settings.get_name()
        if name in DebuggerLog.__loggers:
            console_filter = DebuggerLog.__loggers[name][2]
            with DebuggerLog.__lock:
                console_filter.is_enabled = False

    def resume_console(self):
        """
        Resumes the console output using the previously configured filters.
        """
        name = self.__settings.get_name()
        if name in DebuggerLog.__loggers:
            console_filter = DebuggerLog.__loggers[name][2]
            with DebuggerLog.__lock:
                console_filter.is_enabled = True



    def __create_size_time_rotating_handler(self, filename: str, logLevel):
        config = ConfigManager()
        handler = SizedTimedRotatingFileHandler(filename=filename, backupCount=config.get('LOGGING_BACKUP_COUNT'), maxBytes=self.__settings.get_file_size())
        return self.__config_handler(handler=handler, logLevel=logLevel, rotator=True, is_json=True)

    def __create_stream_handler(self):
        handler = logging.StreamHandler()
        return self.__config_handler(handler=handler, logLevel=logging.DEBUG, rotator=False, is_json=False)

    def __config_handler(self, handler, logLevel, rotator=False, is_json=False):
        config = ConfigManager()
        if is_json:
            fields = config.get(ConfigKey.LOGGING_METADATA, [e.value for e in LogMetadata])
            log_formatter = JsonFormatter(metadata_fields=fields)
        else:
            fields = config.get(ConfigKey.LOGGING_CONSOLE_METADATA, [e.value for e in LogMetadata])
            log_formatter = logging.Formatter(self.__get_log_format(fields), style='{')
        handler.setFormatter(log_formatter)
        handler.setLevel(logLevel)
        if rotator:
            handler.rotator = self.__gzip_rotator
            handler.namer = self.__gzip_namer
        
        return handler

    def __full_path_logs(self):
        logs_base_dir = self.__settings.get_logs_base_dir() if self.__settings.get_logs_base_dir() != "." else os.getcwd()
        config = ConfigManager()
        full_path_logs = os.path.join(logs_base_dir, config.get(ConfigKey.LOGGING_BASE_DIR))
        os.makedirs(full_path_logs, exist_ok=True)
        return full_path_logs

    def __gzip_namer(self, name):
        base_path, roration_ext = os.path.splitext(name)
        path, full_name = os.path.split(base_path)
        base_name, ext = os.path.splitext(full_name)
        handler = self.__get_handler_rotating()
        current_date = datetime.datetime.now().date()

        if handler and handler.rollover == RolloverType.TIME:
            last_record_date = getattr(handler, 'cached_last_date', None)
            current_date = last_record_date or current_date
            
        # Update handler cache for the new file
        if handler:
            handler.cached_last_date = datetime.datetime.now().date()
            handler.rollover = RolloverType.NONE
        
        current_date_str = current_date.strftime("%Y-%m-%d")
        full_path_logs = os.path.join(path, self.__settings.get_backup_dir(), current_date_str)
        os.makedirs(full_path_logs, exist_ok=True)
        
        log_file_name = f"{base_name}_{current_date_str}{roration_ext}{ext}.gz"
        return os.path.join(full_path_logs, log_file_name)

    def __gzip_rotator(self, source, dest):
        with open(source, "rb") as sf, gzip.open(dest, 'wb') as df:
            df.write(sf.read())
        os.remove(source)

    def __get_caller_class(self):
        try:
            # Stack levels:
            # 0: __get_caller_class
            # 1: __log_message
            # 2: debug/info/etc.
            # 3: Caller of debug/info/etc.
            frame = sys._getframe(3)
            if 'self' in frame.f_locals:
                return frame.f_locals['self'].__class__.__name__
        except Exception:
            pass
        return "None"

    def __get_logger(self):        
        return DebuggerLog.__loggers[self.__settings.get_name()][1]

    def __log_message(self, level, message):
        extra = {"caller_class": self.__get_caller_class()}
        
        if isinstance(message, (dict, list, tuple)):
            try:
                message = json.dumps(message, default=str, ensure_ascii=False, indent=2)
            except Exception as e:
                message = f"<[Unserializable Object: {type(message).__name__}] - {e}>"
        elif hasattr(message, '__dict__'):
            try:
                message = json.dumps(message.__dict__, default=str, ensure_ascii=False, indent=2)
            except Exception as e:
                message = f"<[Unserializable Object: {type(message).__name__}] - {e}>"

        self.__get_logger().log(level, message, extra=extra, stacklevel=3)
    
    def __get_handler_rotating(self):
        name = self.__settings.get_name()
        if name in DebuggerLog.__listeners:
            listener = DebuggerLog.__listeners[name]
            for handler in listener.handlers:
                if hasattr(handler, 'rollover') and handler.rollover != RolloverType.NONE:
                    return handler
        return None

    def setLoggerToDebug(self):
        self.setLoggerToLevel(LogLevel.DEBUG)

    def setLoggerToInfo(self):
        self.setLoggerToLevel(LogLevel.INFO)

    def setLoggerToWarning(self):
        self.setLoggerToLevel(LogLevel.WARNING)

    def setLoggerToError(self):
        self.setLoggerToLevel(LogLevel.ERROR)

    def setLoggerToCritical(self):
        self.setLoggerToLevel(LogLevel.CRITICAL)

    def setLoggerToLevel(self, logLevel: LogLevel):
        with DebuggerLog.__lock:
            logger = self.__get_logger()
            logger.setLevel(logLevel.value)
            
            # Update the underlying handlers to respect the level
            name = self.__settings.get_name()
            if name in DebuggerLog.__listeners:
                listener = DebuggerLog.__listeners[name]
                for handler in listener.handlers:
                    if isinstance(handler, SizedTimedRotatingFileHandler):
                        handler.setLevel(logLevel.value)

    def debug(self, message):
        self.__log_message(logging.DEBUG, message)

    def info(self, message):
        self.__log_message(logging.INFO, message)

    def warning(self, message):
        self.__log_message(logging.WARNING, message)

    def error(self, message):
        self.__log_message(logging.ERROR, message)

    def critical(self, message):
        self.__log_message(logging.CRITICAL, message)


class SizedTimedRotatingFileHandler(RotatingFileHandler):
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):        
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.rollover = RolloverType.NONE
        self.cached_last_date = LoggingUtils.get_date_last_record(self.baseFilename)

    def shouldRollover(self, record):
        self.rollover = RolloverType.NONE
        current_date = datetime.datetime.now().date()
        
        if self.cached_last_date is None:
            self.cached_last_date = current_date

        if current_date != self.cached_last_date:
            self.rollover = RolloverType.TIME
            return True

        rollover = super().shouldRollover(record)
        if rollover:
             self.rollover = RolloverType.SIZE
        
        return rollover
