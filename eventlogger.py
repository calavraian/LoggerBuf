import ast
import datetime
import gzip
import logging
import os
import threading
import settings_globals as defaults

from data_logs import main_data_pb2
from logging.handlers import RotatingFileHandler
from debulogger import RolloverType

class LoggingUtils():
    @staticmethod
    def get_date_last_record(file_name):
        last_record = ""
        last_record_date = None
        with open(file_name, 'r') as f:
            for line in reversed(f.readlines()):
                if line.strip():  # Skip empty lines
                    last_record = line.strip()
                    break
        
        if last_record.strip():
            try:
                last_record_bin = ast.literal_eval(last_record)
                event = main_data_pb2.Event.FromString(last_record_bin)
                last_record_date = datetime.datetime.strptime(event.timestamp[:10], "%Y-%m-%d").date()
            except Exception as e:
                print(f"Not valid date extracted from file: {file_name}, line: {last_record}, trying to convert: {last_record[1:11]}, error: {e}")

        return last_record_date

class EventSettings:
    def __init__(
            self,
            logs_base_dir: str = ".",
            backup_dir: str = defaults.EVENT_BACKUP_DIR,
            file_size = defaults.EVENT_FILE_SIZE,
        ):
        """
        Constructor for LoggerSettings.

        Parameters
        ----------
        logs_base_dir : str, optional
            Base directory for events. Defaults to "." (current dir).
        backup_dir : str, optional
            Directory for backup event files. Defaults to "history".
        file_size : int, optional
            Maximum size of each event file in bytes.
        """
        self.__name = defaults.EVENT_LOGGER_NAME
        self.__logs_base_dir = logs_base_dir
        self.__backup_dir = backup_dir
        self.__file_size = file_size
    
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
        Gets the base directory for event file.

        Returns
        -------
        str
            The base directory for event file.
        """
        return self.__logs_base_dir
    
    def get_backup_dir(self):
        """
        Gets the directory for backup event files.

        Returns
        -------
        str
            The directory for backup event files.
        """
        return self.__backup_dir
    
    def get_file_size(self):
        """
        Gets the maximum size of each event file.

        Returns
        -------
        int
            The maximum size of each event file in bytes.
        """

        return self.__file_size

class EventLogger:
    __loggers = {}
    __lock = threading.Lock()

    def __init__(self, settings: EventSettings = None):
        if not settings:
            settings = EventSettings()
        
        EventLogger.__lock.acquire()
        if settings.get_name() not in EventLogger.__loggers:
            self.__settings = settings
            
            full_path_logs = self.__full_path_logs()
            log_file = os.path.join(full_path_logs, f"{defaults.EVENT_MAIN_FILE_NAME}_{self.__settings.get_name()}.log")
            info_handler = self.__create_size_time_rotating_handler(filename=log_file, logLevel=logging.INFO)

            logger = logging.getLogger(self.__settings.get_name())
            logger.addHandler(info_handler)
            logger.setLevel(logging.INFO)

            EventLogger.__loggers[self.__settings.get_name()] = (self.__settings, logger)
        else:
            self.__settings = EventLogger.__loggers[settings.get_name()][0]
        EventLogger.__lock.release()
    
    def __create_size_time_rotating_handler(self, filename: str, logLevel):
        handler = SizedTimedRotatingFileHandler(filename=filename, backupCount=defaults.EVENT_BACKUP_COUNT, maxBytes=self.__settings.get_file_size())
        return self.__config_handler(handler=handler, logLevel=logLevel, rotator=True)

    def __config_handler(self, handler, logLevel, rotator=False):
        handler.setLevel(logLevel)
        if rotator:
            handler.rotator = self.__gzip_rotator
            handler.namer = self.__gzip_namer
        
        return handler

    def __full_path_logs(self):
        logs_base_dir = self.__settings.get_logs_base_dir() if self.__settings.get_logs_base_dir() != "." else os.getcwd()
        full_path_logs = os.path.join(logs_base_dir, defaults.EVENT_BASE_DIR)
        os.makedirs(full_path_logs, exist_ok=True)
        return full_path_logs

    def __gzip_namer(self, name):
        base_path, roration_ext = os.path.splitext(name)
        path, full_name = os.path.split(base_path)
        base_name, ext = os.path.splitext(full_name)
        handler = self.__get_logger().handlers[0]
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
    
    def __get_logger(self):        
        return EventLogger.__loggers[self.__settings.get_name()][1]
        
    def create_event(self, event: main_data_pb2.Event):
        with EventLogger.__lock:
            logger = self.__get_logger()
            event.timestamp = datetime.datetime.now().isoformat()
            serialized_entry = event.SerializeToString()
            threading.Thread(target=logger.info, kwargs={"msg": serialized_entry}).start()

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
