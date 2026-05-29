import datetime
import gzip
import inspect
import logging
import os
import threading
import settings_globals as defaults

from enum import Enum
from logging.handlers import RotatingFileHandler

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
                    # Find the last non-empty line
                    for line in reversed(lines):
                        decoded = line.strip().decode('utf-8', errors='ignore')
                        if decoded:
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
        except Exception as e:
            print(f"Not valid date extracted from last line of {file_name}: '{last_line}', error: {e}")
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
    __log_format = '[{asctime}] >>{name}<< ({file_name}::{caller_class}::{parent_func}->{line_no}) - *{levelname}* - message::>{message}'
    __lock = threading.Lock()

    def __init__(self, settings: LoggerSettings = None):
        if not settings:
            settings = LoggerSettings()
        
        Logger.__lock.acquire()
        if settings.get_name() not in Logger.__loggers:
            self.__settings = settings
            
            full_path_logs = self.__full_path_logs()
            log_file = os.path.join(full_path_logs, f"{defaults.LOGGING_MAIN_FILE_NAME}_{self.__settings.get_name()}.log")
            debug_log_file = os.path.join(full_path_logs, f"{defaults.LOGGING_DEBUG_FILE_NAME}_{self.__settings.get_name()}.log")

            info_handler = self.__create_size_time_rotating_handler(filename=log_file, logLevel=logging.INFO)
            degug_handler = self.__create_size_time_rotating_handler(filename=debug_log_file, logLevel=logging.DEBUG)
            stream_handler = self.__create_stream_handler()

            logger = logging.getLogger(self.__settings.get_name())

            if self.__settings.get_stream() in (StreamLevel.ONLY_FILE, StreamLevel.FILE_CONSOLE):
                logger.addHandler(info_handler)
                logger.addHandler(degug_handler)

            if self.__settings.get_stream() in (StreamLevel.ONLY_CONSOLE, StreamLevel.FILE_CONSOLE):
                logger.addHandler(stream_handler)

            Logger.__loggers[self.__settings.get_name()] = (self.__settings, logger)
        else:
            self.__settings = Logger.__loggers[settings.get_name()][0]
        Logger.__lock.release()

    def __create_file_rotating_handler(self, filename: str, logLevel):
        handler = RotatingFileHandler(filename=filename, backupCount=defaults.LOGGING_BACKUP_COUNT, maxBytes=self.__settings.get_file_size())
        return self.__config_handler(handler=handler, logLevel=logLevel, rotator=True)
    
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

        if handler.rollover == RolloverType.TIME:
            last_record_date = LoggingUtils.get_date_last_record(handler.baseFilename)
            current_date = last_record_date or current_date
        
        current_date_str = current_date.strftime("%Y-%m-%d")
        full_path_logs = os.path.join(path, self.__settings.get_backup_dir(), current_date_str)
        os.makedirs(full_path_logs, exist_ok=True)
        
        log_file_name = f"{base_name}_{current_date_str}{roration_ext}{ext}.gz"
        handler.rollover == RolloverType.NONE
        return os.path.join(full_path_logs, log_file_name)

    def __gzip_rotator(self, source, dest):
        with open(source, "rb") as sf, gzip.open(dest, 'wb') as df:
            df.write(sf.read())
        os.remove(source)

    def __parent_func(self):
        frame = self.__get_inspect_frame()
        return frame.f_code.co_name

    def __parent_file_name(self):
        frame = self.__get_inspect_frame()
        return os.path.split(frame.f_code.co_filename)[1]

    def __parent_line_no(self):
        frame = self.__get_inspect_frame()
        return frame.f_code.co_firstlineno
    
    def __caller_class_name(self):
        frame = self.__get_inspect_frame()
        return frame.f_locals.get('self', None).__class__.__name__ if 'self' in frame.f_locals else None
    
    def __get_inspect_frame(self, steps=5):
        frame = inspect.currentframe()
        while steps > 0:
            if frame.f_back:
                frame = frame.f_back
            else:
                break
            steps -= 1
        return frame

    def __get_logger(self):        
        return Logger.__loggers[self.__settings.get_name()][1]
    
    def __get_extras(self):
        return {"file_name": self.__parent_file_name(), "caller_class": self.__caller_class_name(), "parent_func": self.__parent_func(), "line_no": self.__parent_line_no()}

    def __log_message(self, message, method):
        with Logger.__lock:
            threading.Thread(target=method, kwargs={"msg": message, "extra": self.__get_extras()}).start()
    
    def __get_handler_rotating(self):
        logger = self.__get_logger()
        for handler in logger.handlers:
            if handler.rollover != RolloverType.NONE:
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
        self.__log_message(message=message, method=self.__get_logger().debug)

    def info(self, message):
        self.__log_message(message=message, method=self.__get_logger().info)

    def warning(self, message):
        self.__log_message(message=message, method=self.__get_logger().warning)

    def error(self, message):
        self.__log_message(message=message, method=self.__get_logger().error)

    def critical(self, message):
        self.__log_message(message=message, method=self.__get_logger().critical)

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
