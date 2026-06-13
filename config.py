import json
import os
import threading
import time
from enum import Enum


class ConfigKey(str, Enum):
    LOG_LEVEL = "LOG_LEVEL"
    LOGGING_BASE_DIR = "LOGGING_BASE_DIR"
    LOGGING_BACKUP_DIR = "LOGGING_BACKUP_DIR"
    LOGGING_MAIN_FILE_NAME = "LOGGING_MAIN_FILE_NAME"
    LOGGING_DEBUG_FILE_NAME = "LOGGING_DEBUG_FILE_NAME"
    LOGGING_BACKUP_COUNT = "LOGGING_BACKUP_COUNT"
    LOGGING_LOGGER_NAME = "LOGGING_LOGGER_NAME"
    LOGGING_FILE_SIZE = "LOGGING_FILE_SIZE"
    LOGGING_QUEUE_MAX_SIZE = "LOGGING_QUEUE_MAX_SIZE"
    LOGGING_QUEUE_STRATEGY = "LOGGING_QUEUE_STRATEGY"
    LOGGING_CONSOLE_ENABLED = "LOGGING_CONSOLE_ENABLED"
    LOGGING_CONSOLE_ALLOWED_CLASSES = "LOGGING_CONSOLE_ALLOWED_CLASSES"
    LOGGING_CONSOLE_ALLOWED_LEVELS = "LOGGING_CONSOLE_ALLOWED_LEVELS"
    LOGGING_METADATA = "LOGGING_METADATA"
    LOGGING_CONSOLE_METADATA = "LOGGING_CONSOLE_METADATA"
    LOGGING_DESTINATION = "LOGGING_DESTINATION"

    EVENT_BASE_DIR = "EVENT_BASE_DIR"
    EVENT_BACKUP_DIR = "EVENT_BACKUP_DIR"
    EVENT_MAIN_FILE_NAME = "EVENT_MAIN_FILE_NAME"
    EVENT_BACKUP_COUNT = "EVENT_BACKUP_COUNT"
    EVENT_LOGGER_NAME = "EVENT_LOGGER_NAME"
    EVENT_FILE_SIZE = "EVENT_FILE_SIZE"
    EVENT_QUEUE_MAX_SIZE = "EVENT_QUEUE_MAX_SIZE"
    EVENT_QUEUE_STRATEGY = "EVENT_QUEUE_STRATEGY"

class LogMetadata(str, Enum):
    TIMESTAMP = "TIMESTAMP"
    LOGGER = "LOGGER"
    LEVEL = "LEVEL"
    FILE = "FILE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    LINE = "LINE"

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
    "LOGGING_DESTINATION": "CONSOLE",
    "EVENT_BASE_DIR": "events",
    "EVENT_BACKUP_DIR": "history",
    "EVENT_MAIN_FILE_NAME": "events",
    "EVENT_BACKUP_COUNT": 5,
    "EVENT_LOGGER_NAME": "MAIN",
    "EVENT_FILE_SIZE": 1024,
    "EVENT_QUEUE_MAX_SIZE": 10000,
    "EVENT_QUEUE_STRATEGY": "LOSSLESS",
    "LOGGING_CONSOLE_ENABLED": True,
    "LOGGING_CONSOLE_ALLOWED_CLASSES": [],
    "LOGGING_CONSOLE_ALLOWED_LEVELS": [],
    "LOGGING_METADATA": ["TIMESTAMP", "LOGGER", "LEVEL", "FILE", "CLASS", "FUNCTION", "LINE"],
    "LOGGING_CONSOLE_METADATA": ["TIMESTAMP", "LOGGER", "LEVEL", "FILE", "CLASS", "FUNCTION", "LINE"]
}

class ConfigManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigManager, cls).__new__(cls)
                cls._instance._config = {}
                cls._instance._subscribers = {}
                cls._instance._last_mtime = 0
                cls._instance._watcher_thread = None
                cls._instance._is_watching = False
                cls._instance.load()
                cls._instance._start_watcher()
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
        if isinstance(key, Enum):
            key = key.value
        if key in self._config:
            return self._config[key]
        if key in DEFAULT_CONFIG:
            return DEFAULT_CONFIG[key]
        return default_value

    def set(self, key, value):
        if isinstance(key, Enum):
            key = key.value
        changed = False
        with self._lock:
            old_value = self._config.get(key)
            self._config[key] = value
            self.save()
            if old_value != value:
                changed = True
        
        if changed:
            self._notify(key, value)

    def remove(self, key):
        if isinstance(key, Enum):
            key = key.value
        changed = False
        with self._lock:
            if key in self._config:
                del self._config[key]
                self.save()
                changed = True
        
        if changed:
            self._notify(key, self.get(key))

    def save(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error saving {CONFIG_FILE}: {e}")

    def subscribe(self, key, callback):
        if isinstance(key, Enum):
            key = key.value
        with self._lock:
            if key not in self._subscribers:
                self._subscribers[key] = []
            if callback not in self._subscribers[key]:
                self._subscribers[key].append(callback)

    def _notify(self, key, new_value):
        subscribers = self._subscribers.get(key, [])
        for callback in subscribers:
            try:
                callback(new_value)
            except Exception as e:
                print(f"Error notifying subscriber for config {key}: {e}")

    def _start_watcher(self):
        if self._is_watching:
            return
        self._is_watching = True

        def watcher():
            while self._is_watching:
                try:
                    if os.path.exists(CONFIG_FILE):
                        mtime = os.path.getmtime(CONFIG_FILE)
                        if mtime > self._last_mtime:
                            self._last_mtime = mtime
                            changes = []
                            with self._lock:
                                old_config = dict(self._config)
                                self.load()
                                # Check what changed
                                for key in self._config:
                                    if old_config.get(key) != self._config[key]:
                                        changes.append((key, self._config[key]))
                            for key, val in changes:
                                self._notify(key, val)
                except Exception as e:
                    pass
                time.sleep(5)

        self._watcher_thread = threading.Thread(target=watcher, daemon=True, name="ConfigWatcher_Global")
        self._watcher_thread.start()
