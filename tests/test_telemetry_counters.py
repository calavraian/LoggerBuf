import pytest
from loggerbuf.telemetry import TelemetryLog, EventSettings, MetricSettings
from loggerbuf.config import ConfigManager
import time
import os

def test_metrics_disabled_by_default(tmp_path):
    config = ConfigManager()
    config.set('METRICS_ENABLED', False)
    
    settings = EventSettings(name=f"TEST_NO_METRICS_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    assert getattr(telemetry, '_TelemetryLog__metric_writer') is None
    
    # This shouldn't crash, it should just return early
    telemetry.increment(1)

def test_metrics_enabled_initialization(tmp_path):
    config = ConfigManager()
    config.set('METRICS_ENABLED', True)
    
    settings = EventSettings(name=f"TEST_METRICS_INIT_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    metric_writer = getattr(telemetry, '_TelemetryLog__metric_writer')
    assert metric_writer is not None
    assert metric_writer.worker_thread.is_alive()
    
    metric_writer.stop()
    telemetry._TelemetryLog__event_writer.stop()
    config.set('METRICS_ENABLED', False)

def test_metric_file_separation_and_increment(tmp_path):
    config = ConfigManager()
    config.set('METRICS_ENABLED', True)
    
    # We must clear the TelemetryLog instances cache for a clean test because it is a singleton based on name
    import loggerbuf.telemetry as tel
    tel.TelemetryLog._TelemetryLog__instances.clear()

    settings = EventSettings(name=f"TEST_SEP_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    # 1 is generally a valid counter_type since enum defaults start at 1
    telemetry.increment(1, value=5)
    
    event_writer = telemetry._TelemetryLog__event_writer
    metric_writer = telemetry._TelemetryLog__metric_writer
    
    metric_writer.queue.join()
    time.sleep(0.1)
    
    event_file = event_writer.current_filename
    metric_file = metric_writer.current_filename
    
    # Verify different directories/files
    assert "events_TEST_SEP" in event_file
    assert "counters_TEST_SEP" in metric_file
    assert event_file != metric_file
    
    assert os.path.exists(metric_file)
    assert os.path.getsize(metric_file) > 0
    
    metric_writer.stop()
    event_writer.stop()
    config.set('METRICS_ENABLED', False)

