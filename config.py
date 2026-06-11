import json
import os
import threading
import settings_globals as defaults

CONFIG_FILE = "loggerbuf.json"

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
                self._config = {}
        else:
            self._config = {}

    def get(self, key, default_value=None):
        if key in self._config:
            return self._config[key]
        return getattr(defaults, key, default_value)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error saving {CONFIG_FILE}: {e}")
