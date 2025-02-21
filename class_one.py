from data_logs import main_data_pb2, event_status_pb2, event_example_pb2
from debulogger import Logger, StreamLevel, LoggerSettings
from eventlogger import EventLogger

"""
This class is an example of how to use the EventLogger class to log events
and the Logger class to log messages.

This class can be removed from the project.
"""
class ExampleClientClass:
    def __init__(self):
        loggerSettings = LoggerSettings(name='MAIN_LOGIC', stream=StreamLevel.FILE_CONSOLE)
        self.logger = Logger(loggerSettings)
        self.logger.setLoggerToDebug()

        self.eventLogger = EventLogger()

    def operation(self):
        self.logger.debug("Esto es un debug")
        self.logger.info("Esto es un info - primer mensaje")
        self.logger.info("Esto es un info - segundo mensaje")

    def log_message(self):
        example_event = event_example_pb2.ExampleSubEvent()
        example_event.name = "Event name 1 here"
        example_event.description = "Event description for event 1"
        example_event.counter = 1
        example_event.operation_type = event_example_pb2.ExampleSubEvent.OperationType.OPERATION_DATA_READ

        main_data = main_data_pb2.Event()
        main_data.event_type = event_status_pb2.EventTypes.EXAMPLE_EVENT_API_INVOKED
        main_data.general_note = "Example not for event"
        main_data.status = event_status_pb2.Status.EXAMPLE_EVENT_STATUS_STARTED
        main_data.example_sub_event.CopyFrom(example_event)

        self.eventLogger.create_event(main_data)

if __name__ == "__main__":
    class_one = ExampleClientClass()
    class_one.operation()
    class_one.log_message()
