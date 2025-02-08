import datetime

from data_logs import klaks_logging_pb2, generic_log_pb2
from debulogger import Logger, StreamLevel, LoggerSettings

class ClassOne:
    def __init__(self):
        loggerSettings = LoggerSettings(name='MAIN_LOGIC', stream=StreamLevel.FILE_CONSOLE)
        self.logger = Logger(loggerSettings)
        self.logger.setLoggerToDebug()

    def operation(self):
        self.logger.debug("Esto es un debug")
        self.logger.info("Esto es un info - primer mensaje")
        self.logger.info("Esto es un info - segundo mensaje")

    def log_message(self, level, message, metadata={}):
        generic_log = generic_log_pb2.Generic_log()
        generic_log.message = "Message inside generic log"
        generic_log.status = generic_log_pb2.Generic_log.Status.STATUS_ACTIVE

        log_entry = klaks_logging_pb2.Klaks_LogEntry()
        log_entry.timestamp = datetime.datetime.now().isoformat()
        log_entry.level = level
        log_entry.message = message
        log_entry.metadata.update(metadata)
        log_entry.generic_log.CopyFrom(generic_log)

        # Serialize to bytes
        serialized_entry = log_entry.SerializeToString()
        print(log_entry)
        print("---")
        print(serialized_entry.decode('utf-8'))
        print("---")
        print("---")
        print(klaks_logging_pb2.Klaks_LogEntry.FromString(serialized_entry))

if __name__ == "__main__":
    class_one = ClassOne()
    # class_one.log_message(level='INFO', message='Esto es un info', metadata={'file_name': 'class_one.py', 'caller_class': 'class_one'})
    class_one.operation()
    print("fin main")
