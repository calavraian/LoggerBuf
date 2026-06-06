import datetime
import gzip
import logging
import os
import queue
import sys
import threading
import settings_globals as defaults

from enum import Enum
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener

class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class StreamLevel(Enum):
    ONLY_CONSOLE = 1
    ONLY_FILE = 2
    FILE_CONSOLE = 3

class RolloverType(Enum):
    NONE = 0
    TIME = 1
    SIZE = 2

from settings_globals import QueueStrategy

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
                buffer_size = 1024
                # Move backwards in chunks of 1KB
                while position > 0:
                    read_size = min(buffer_size, position)
                    position -= read_size
                    f.seek(position, os.SEEK_SET)
                    chunk = f.read(read_size)
                    
                    # Split lines by binary newline
                    lines = chunk.split(b'\n')
                    # Find the last non-empty line starting with '[' (log bracket)
                    for line in reversed(lines):
                        decoded = line.strip().decode('utf-8', errors='ignore')
                        if decoded and decoded.startswith("["):
                            last_line = decoded
                            break
                    if last_line:
                        break
        except Exception as e:
            print(f"Error reading last record of {file_name}: {e}")
            return None

        if not last_line:
            return None
            
        try:
            date_str = last_line[1:11]
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return None



class LoggerSettings:
    def __init__(
            self,
            name: str = defaults.LOGGING_LOGGER_NAME,
            logs_base_dir: str = ".",
            backup_dir: str = defaults.LOGGING_BACKUP_DIR,
            file_size = defaults.LOGGING_FILE_SIZE,
            stream: StreamLevel = StreamLevel.ONLY_FILE,
        ):
        """
        Constructor for LoggerSettings.

        Parameters
        ----------
        name : str
            Name of the logger.
        logs_base_dir : str, optional
            Base directory for logs. Defaults to "." (current dir).
        backup_dir : str, optional
            Directory for backup logs. Defaults to "history".
        file_size : int, optional
            Maximum size of each log file in bytes.
        stream : StreamLevel, optional
            Stream level for logging. Defaults to StreamLevel.ONLY_FILE.
        """
        self.__name = name
        self.__logs_base_dir = logs_base_dir
        self.__backup_dir = backup_dir
        self.__file_size = file_size
        self.__stream = stream
    
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
        StreamLevel
            The stream type for the logger.
        """
        return self.__stream

class Logger:
    __loggers = {}
    __listeners = {}
    __log_format = '[{asctime}] >>{name}<< ({filename}::{caller_class}::{funcName}->{lineno}) - *{levelname}* - message::>{message}'
    __lock = threading.Lock()

    def __init__(self, settings: LoggerSettings = None):
        if not settings:
            settings = LoggerSettings()
        
        with Logger.__lock:
            name = settings.get_name()
            if name not in Logger.__loggers:
                self.__settings = settings
                
                # Retrieve configuration with safe defaults
                queue_max_size = getattr(defaults, 'LOGGING_QUEUE_MAX_SIZE', 10000)
                queue_strategy = getattr(defaults, 'LOGGING_QUEUE_STRATEGY', QueueStrategy.LOSSY)
                
                full_path_logs = self.__full_path_logs()
                log_file = os.path.join(full_path_logs, f"{defaults.LOGGING_MAIN_FILE_NAME}_{name}.log")
                debug_log_file = os.path.join(full_path_logs, f"{defaults.LOGGING_DEBUG_FILE_NAME}_{name}.log")

                info_handler = self.__create_size_time_rotating_handler(filename=log_file, logLevel=logging.INFO)
                debug_handler = self.__create_size_time_rotating_handler(filename=debug_log_file, logLevel=logging.DEBUG)
                stream_handler = self.__create_stream_handler()

                # Initialize console filter based on settings
                console_enabled = self.__settings.get_stream() in (StreamLevel.ONLY_CONSOLE, StreamLevel.FILE_CONSOLE)
                console_filter = ConsoleFilter(is_enabled=console_enabled)
                stream_handler.addFilter(console_filter)
                
                dest_handlers = []
                if self.__settings.get_stream() in (StreamLevel.ONLY_FILE, StreamLevel.FILE_CONSOLE):
                    dest_handlers.append(info_handler)
                    dest_handlers.append(debug_handler)

                # Always add stream_handler, output is controlled by ConsoleFilter
                dest_handlers.append(stream_handler)

                # Initialize Queue
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

                Logger.__loggers[name] = (self.__settings, logger, console_filter)
                Logger.__listeners[name] = listener
            else:
                self.__settings = Logger.__loggers[name][0]

    def enable_console(self, allowed_classes: list = None, allowed_levels: list = None):
        """
        Dynamically enables the console output.
        Optionally filters by a list of class names or log levels.
        """
        name = self.__settings.get_name()
        if name in Logger.__loggers:
            console_filter = Logger.__loggers[name][2]
            with Logger.__lock:
                console_filter.allowed_classes = allowed_classes
                console_filter.allowed_levels = allowed_levels
                console_filter.is_enabled = True

    def disable_console(self):
        """
        Dynamically disables the console output.
        """
        name = self.__settings.get_name()
        if name in Logger.__loggers:
            console_filter = Logger.__loggers[name][2]
            with Logger.__lock:
                console_filter.is_enabled = False


    def __create_size_time_rotating_handler(self, filename: str, logLevel):
        handler = SizedTimedRotatingFileHandler(filename=filename, backupCount=defaults.LOGGING_BACKUP_COUNT, maxBytes=self.__settings.get_file_size())
        return self.__config_handler(handler=handler, logLevel=logLevel, rotator=True)

    def __create_stream_handler(self):
        handler = logging.StreamHandler()
        return self.__config_handler(handler=handler, logLevel=logging.DEBUG)

    def __config_handler(self, handler, logLevel, rotator=False):
        log_formatter = logging.Formatter(Logger.__log_format, style='{')
        handler.setFormatter(log_formatter)
        handler.setLevel(logLevel)
        if rotator:
            handler.rotator = self.__gzip_rotator
            handler.namer = self.__gzip_namer
        
        return handler

    def __full_path_logs(self):
        logs_base_dir = self.__settings.get_logs_base_dir() if self.__settings.get_logs_base_dir() != "." else os.getcwd()
        full_path_logs = os.path.join(logs_base_dir, defaults.LOGGING_BASE_DIR)
        os.makedirs(full_path_logs, exist_ok=True)
        return full_path_logs

    def __gzip_namer(self, name):
        base_path, roration_ext = os.path.splitext(name)
        path, full_name = os.path.split(base_path)
        base_name, ext = os.path.splitext(full_name)
        handler = self.__get_handler_rotating()
        current_date = datetime.datetime.now().date()

        if handler and handler.rollover == RolloverType.TIME:
            last_record_date = LoggingUtils.get_date_last_record(handler.baseFilename)
            current_date = last_record_date or current_date
        
        current_date_str = current_date.strftime("%Y-%m-%d")
        full_path_logs = os.path.join(path, self.__settings.get_backup_dir(), current_date_str)
        os.makedirs(full_path_logs, exist_ok=True)
        
        log_file_name = f"{base_name}_{current_date_str}{roration_ext}{ext}.gz"
        if handler:
            handler.rollover == RolloverType.NONE
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
        return Logger.__loggers[self.__settings.get_name()][1]

    def __log_message(self, level, message):
        extra = {"caller_class": self.__get_caller_class()}
        self.__get_logger().log(level, message, extra=extra, stacklevel=3)
    
    def __get_handler_rotating(self):
        name = self.__settings.get_name()
        if name in Logger.__listeners:
            listener = Logger.__listeners[name]
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
        with Logger.__lock:
            self.__get_logger().setLevel(logLevel.value)

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

    def shouldRollover(self, record):
        self.rollover = RolloverType.NONE
        last_record_date = LoggingUtils.get_date_last_record(self.baseFilename)
        current_date = datetime.datetime.now().date()

        if last_record_date and current_date != last_record_date:
            self.rollover = RolloverType.TIME
            return True

        rollover = super().shouldRollover(record)
        if rollover:
             self.rollover = RolloverType.SIZE
        
        return rollover
