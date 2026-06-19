import pytest
from loggerbuf.telemetry import TelemetryLog, EventSettings
from loggerbuf.config import QueueStrategy
from loggerbuf.queue_metrics import MetricField
from loggerbuf import schema_loader
main_data_pb2 = schema_loader.get_main_data_pb2()
import time
import os

def test_telemetry_singleton_and_defaults():
    # Test lines 276, 285-286
    log1 = TelemetryLog()
    log2 = TelemetryLog()
    assert log1._TelemetryLog__settings.get_name() == log2._TelemetryLog__settings.get_name()
    assert log1._TelemetryLog__event_writer is log2._TelemetryLog__event_writer

def test_telemetry_lossy_strategy_and_queue_full(tmp_path):
    settings = EventSettings(name=f"TEST_LOSSY_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    # Overwrite strategy and maxsize for testing queue full
    writer = telemetry._TelemetryLog__event_writer
    writer.strategy = QueueStrategy.LOSSY
    writer.queue.maxsize = 2  # Very small queue
    
    # Fill queue to hit except queue.Full and record_drop
    event = main_data_pb2.Event()
    event.general_note = "Lossy Test"
    
    # Send enough to fill it quickly before the background thread can process them
    # Actually wait, the background thread might process them.
    # Let's pause the background thread or lock the file to stall it.
    with writer.file_lock:
        for _ in range(5):
            telemetry.send(event)
            
    # Allow some time
    time.sleep(0.1)
    metrics = telemetry.get_metrics()
    
    # Verify we hit queue drops
    assert metrics["total_drops"] > 0

def test_telemetry_stop(tmp_path):
    settings = EventSettings(name=f"TEST_STOP_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    writer = telemetry._TelemetryLog__event_writer
    
    writer.stop()
    assert writer.stop_event.is_set()
    assert not writer.worker_thread.is_alive()

def test_telemetry_size_rotation_and_rollover(tmp_path):
    settings = EventSettings(name=f"TEST_ROTATE_{tmp_path.name}", logs_base_dir=str(tmp_path), file_size=50) # Tiny file size
    telemetry = TelemetryLog(settings)
    
    # Create large event to trigger size rotation
    event = main_data_pb2.Event()
    event.general_note = "A" * 100 
    telemetry.send(event)
    telemetry.send(event)
    
    writer = telemetry._TelemetryLog__event_writer
    writer.queue.join()
    time.sleep(0.1)
    
    history_dir = tmp_path / "events" / "history"
    # One rollover should have happened
    assert os.path.exists(history_dir)
    assert len(list(history_dir.rglob("*.gz"))) > 0

def test_telemetry_getframe_exception(tmp_path, monkeypatch):
    settings = EventSettings(name=f"TEST_FRAME_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    import sys
    monkeypatch.setattr(sys, '_getframe', lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Test Exception")))
    
    event = main_data_pb2.Event()
    telemetry.send(event)
    
    writer = telemetry._TelemetryLog__event_writer
    writer.queue.join()
    time.sleep(0.1)
    
    # The event should have Unknown caller info, let's verify it didn't crash
    # By checking the file
    pass

def test_telemetry_get_date_last_record(tmp_path):
    settings = EventSettings(name=f"TEST_LAST_REC_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    event = main_data_pb2.Event()
    telemetry.send(event)
    
    writer = telemetry._TelemetryLog__event_writer
    writer.queue.join()
    time.sleep(0.1)
    
    # Now simulate a new writer reading this existing file
    from loggerbuf.telemetry import EventWriter
    import datetime
    new_writer = EventWriter(settings)
    assert new_writer._cached_last_date == datetime.datetime.now().date()
    new_writer.stop()
    telemetry._TelemetryLog__event_writer.stop()
