import datetime
import gzip
import inspect
import logging
import os
import threading

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

class RotatingFrequency(Enum):
    DAYLY = 1
    EVERY_OTHER_DAY = 2
    WEEKLY = 3
    MONTHLY = 4

class LoggerSettings:
    def __init__(self, name: str, logs_base_dir: str = ".", backup_dir: str = "history", file_size=1024 , stream: StreamLevel = StreamLevel.ONLY_FILE, frequency: RotatingFrequency = RotatingFrequency.DAYLY):
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
            Maximum size of each log file in bytes. Defaults to 1024.
        stream : StreamLevel, optional
            Stream level for logging. Defaults to StreamLevel.ONLY_FILE.
        frequency : RotatingFrequency, optional
            Frequency for log rotation. Defaults to RotatingFrequency.DAYLY.
        """
        self.__name = name
        self.__logs_base_dir = logs_base_dir
        self.__backup_dir = backup_dir
        self.__file_size = file_size
        self.__stream = stream
        self.__frequency = frequency
    
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
    
    def get_frequency(self):
        """
        Gets the frequency for log rotation.

        Returns
        -------
        RotatingFrequency
            The frequency for log rotation.
        """
        return self.__frequency

class Logger:
    __loggers = {}
    __log_dir = "logs"
    __log_file = "logs"
    __debug_log_file = "debug_logs"
    __backup_count = 5
    __log_format = '[{asctime}] >>{name}<< ({file_name}::{caller_class}::{parent_func}->{line_no}) - *{levelname}* - message::>{message}'
    __lock = threading.Lock()

    def __init__(self, settings: LoggerSettings):
        Logger.__lock.acquire()
        if settings.get_name() not in Logger.__loggers:
            self.__settings = settings
            
            full_path_logs = self.__full_path_logs()
            log_file = os.path.join(full_path_logs, f"{Logger.__log_file}_{self.__settings.get_name()}.log")
            debug_log_file = os.path.join(full_path_logs, f"{Logger.__debug_log_file}_{self.__settings.get_name()}.log")

            info_handler = self.__create_rotating_handler(filename=log_file, logLevel=logging.INFO)
            degug_handler = self.__create_rotating_handler(filename=debug_log_file, logLevel=logging.DEBUG)
            stream_handler = self.__create_stream_handler()

            logger = logging.getLogger(self.__settings.get_name())

            if self.__settings.get_stream() in (StreamLevel.ONLY_FILE, StreamLevel.FILE_CONSOLE):
                logger.addHandler(degug_handler)
                logger.addHandler(info_handler)

            if self.__settings.get_stream() in (StreamLevel.ONLY_CONSOLE, StreamLevel.FILE_CONSOLE):
                logger.addHandler(stream_handler)

            Logger.__loggers[self.__settings.get_name()] = (self.__settings, logger)
        else:
            self.__settings = Logger.__loggers[settings.get_name()][0]
        Logger.__lock.release()

    def __create_rotating_handler(self, filename: str, logLevel):
        log_formatter = logging.Formatter(Logger.__log_format, style='{')
        handler = RotatingFileHandler(filename=filename, backupCount=Logger.__backup_count, maxBytes=self.__settings.get_file_size())
        handler.rotator = self.__gzip_rotator
        handler.namer = self.__gzip_namer
        handler.setFormatter(log_formatter)
        handler.setLevel(logLevel)
        return handler
    
    def __create_stream_handler(self):
        log_formatter = logging.Formatter(Logger.__log_format, style='{')
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        stream_handler.setLevel(logging.DEBUG)
        return stream_handler

    def __full_path_logs(self):
        logs_base_dir = self.__settings.get_logs_base_dir() if self.__settings.get_logs_base_dir() != "." else os.getcwd()
        full_path_logs = os.path.join(logs_base_dir, Logger.__log_dir)
        os.makedirs(full_path_logs, exist_ok=True)
        return full_path_logs

    def __gzip_namer(self, name):
        base_path, roration_ext = os.path.splitext(name)
        path, full_name = os.path.split(base_path)
        base_name, ext = os.path.splitext(full_name)

        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        full_path_logs = os.path.join(path, self.__settings.get_backup_dir(), current_date)
        os.makedirs(full_path_logs, exist_ok=True)
        
        log_file_name = f"{base_name}_{current_date}{ext}{roration_ext}.gz"
        return os.path.join(full_path_logs, log_file_name)

    def __gzip_rotator(self, source, dest):
        with open(source, "rb") as sf, gzip.open(dest, 'wb', )as df:
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
