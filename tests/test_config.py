import unittest
import os
import json
from config import ConfigManager, CONFIG_FILE
from debugger import DebuggerLog, LogLevel
import logging

class TestConfig(unittest.TestCase):
    def setUp(self):
        # Reset singleton and file
        ConfigManager._instance = None
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            
    def tearDown(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        ConfigManager._instance = None

    def test_config_defaults(self):
        config = ConfigManager()
        # Test a known default from settings_globals
        self.assertEqual(config.get('LOGGING_FILE_SIZE'), 1024)

    def test_config_set_get(self):
        config = ConfigManager()
        config.set('LOG_LEVEL', 'INFO')
        self.assertEqual(config.get('LOG_LEVEL'), 'INFO')
        
        # Verify file was written
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        self.assertEqual(data['LOG_LEVEL'], 'INFO')

    def test_config_reload(self):
        config = ConfigManager()
        config.set('TEST_VAL', 123)
        
        # Simulate external modification
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'TEST_VAL': 456}, f)
            
        config.load()
        self.assertEqual(config.get('TEST_VAL'), 456)

    def test_config_remove(self):
        config = ConfigManager()
        config.set('LOG_LEVEL', 'CRITICAL')
        self.assertEqual(config.get('LOG_LEVEL'), 'CRITICAL')
        
        config.remove('LOG_LEVEL')
        self.assertEqual(config.get('LOG_LEVEL'), 'DEBUG') # Default from DEFAULT_CONFIG

if __name__ == '__main__':
    unittest.main()
