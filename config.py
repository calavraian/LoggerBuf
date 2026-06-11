import json
import os
import threading
from enum import Enum

class QueueStrategy(Enum):
    LOSSY = 1
    LOSSLESS = 2

CONFIG_FILE = "loggerbuf.json"

DEFAULT_CONFIG = {
    "LOG_LEVEL": "DEBUG",
    "LOGGING_BASE_DIR": "logs",
    "LOGGING_BACKUP_DIR": "history",
    "LOGGING_MAIN_FILE_NAME": "logs",
    "LOGGING_DEBUG_FILE_NAME": "debug_logs",
    "LOGGING_BACKUP_COUNT": 5,
    "LOGGING_LOGGER_NAME": "MAIN",
    "LOGGING_FILE_SIZE": 1024,
    "LOGGING_QUEUE_MAX_SIZE": 10000,
    "LOGGING_QUEUE_STRATEGY": "LOSSY",
    "EVENT_BASE_DIR": "events",
    "EVENT_BACKUP_DIR": "history",
    "EVENT_MAIN_FILE_NAME": "events",
    "EVENT_BACKUP_COUNT": 5,
    "EVENT_LOGGER_NAME": "MAIN",
    "EVENT_FILE_SIZE": 1024,
    "EVENT_QUEUE_MAX_SIZE": 10000,
    "EVENT_QUEUE_STRATEGY": "LOSSLESS"
}

class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigManager, cls).__new__(cls)
                cls._instance._config = {}
                cls._instance.load()
            return cls._instance

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"Error loading {CONFIG_FILE}: {e}")
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save()  # Generate default file on first run

    def get(self, key, default_value=None):
        if key in self._config:
            return self._config[key]
        if key in DEFAULT_CONFIG:
            return DEFAULT_CONFIG[key]
        return default_value

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error saving {CONFIG_FILE}: {e}")
