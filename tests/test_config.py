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

    def test_config_validation(self):
        config = ConfigManager()
        
        # Valid cases (case insensitive)
        config.set('LOG_LEVEL', 'critical')
        self.assertEqual(config.get('LOG_LEVEL'), 'CRITICAL')
        
        config.set('METRICS_ENABLED', 'true')
        self.assertEqual(config.get('METRICS_ENABLED'), True)
        
        config.set('METRICS_ENABLED', False)
        self.assertEqual(config.get('METRICS_ENABLED'), False)
        
        # Invalid cases
        with self.assertRaises(ValueError):
            config.set('LOG_LEVEL', 'INVALID_LEVEL')
            
        with self.assertRaises(ValueError):
            config.set('EVENT_QUEUE_STRATEGY', 'FAST')

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

    def test_config_load_no_overwrite(self):
        # Create a config file first
        custom_data = {"LOG_LEVEL": "CRITICAL"}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(custom_data, f)
        
        # Instantiate ConfigManager (like 'init' command does)
        config = ConfigManager()
        
        # Check that it loaded our custom file instead of generating defaults
        self.assertEqual(config.get('LOG_LEVEL'), 'CRITICAL')
        
        # Ensure the file still has our custom data and wasn't overwritten
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        self.assertEqual(data['LOG_LEVEL'], 'CRITICAL')

if __name__ == '__main__':
    unittest.main()
