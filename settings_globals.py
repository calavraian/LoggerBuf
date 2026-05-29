# Settings for debulogger
LOGGING_BASE_DIR = "logs"
LOGGING_BACKUP_DIR = "history"
LOGGING_MAIN_FILE_NAME = "logs"
LOGGING_DEBUG_FILE_NAME = "debug_logs"
LOGGING_BACKUP_COUNT = 5
LOGGING_LOGGER_NAME = "MAIN"
LOGGING_FILE_SIZE = 1024
LOGGING_QUEUE_MAX_SIZE = 10000
LOGGING_QUEUE_STRATEGY = "lossy"  # Options: 'lossless' (block client) or 'lossy' (drop logs)

# Settings for eventlogger
EVENT_BASE_DIR = "events"
EVENT_BACKUP_DIR = "history"
EVENT_MAIN_FILE_NAME = "events"
EVENT_BACKUP_COUNT = 5
EVENT_LOGGER_NAME = "MAIN"
EVENT_FILE_SIZE = 1024
EVENT_QUEUE_MAX_SIZE = 10000
EVENT_QUEUE_STRATEGY = "lossless"  # Options: 'lossless' (block client) or 'lossy' (drop events)

