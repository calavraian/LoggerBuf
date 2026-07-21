import os
import time
import pytest
from unittest.mock import MagicMock
from loggerbuf.telemetry import TelemetryLog, EventSettings, EventContext
from loggerbuf import schema_loader
main_data_pb2 = schema_loader.get_main_data_pb2()
registry_pb2 = schema_loader.get_registry_pb2()
demo_event_pb2 = schema_loader.get_module("demo_event_pb2")
from loggerbuf.config import QueueStrategy
import struct

class DummyTelemetryCaller:
    def execute_telemetry(self, telemetry_logger):
        event = main_data_pb2.Event()
        event.event_type = registry_pb2.EventType.EVENT_DATA_BASE_PROCESSING
        event.general_note = "Strict Context Test"
        event.status = registry_pb2.EventStatus.STATUS_COMPLETED
        
        telemetry_logger.send(event)

def test_telemetry_injections_and_nested_protos(tmp_path):
    settings = EventSettings(
        name="TEST_TELEMETRY",
        logs_base_dir=str(tmp_path)
    )
    # Re-initialize to ensure fresh state
    telemetry = TelemetryLog(settings)
    
    caller = DummyTelemetryCaller()
    caller.execute_telemetry(telemetry)
    
    # Allow the background worker to flush to disk
    telemetry._TelemetryLog__event_writer.queue.join()
    time.sleep(0.1)
    
    events_dir = tmp_path / "events"
    assert events_dir.exists()
    
    event_files = list(events_dir.glob("events_TEST_TELEMETRY.log"))
    assert len(event_files) == 1
    
    # Read binary length-prefixed format
    with open(event_files[0], "rb") as f:
        length_bytes = f.read(4)
        assert len(length_bytes) == 4
        
        length = struct.unpack(">I", length_bytes)[0]
        assert length > 0
        
        payload = f.read(length)
        assert len(payload) == length
        
        decoded_event = main_data_pb2.Event()
        decoded_event.ParseFromString(payload)
        
        # Verify custom notes
        assert decoded_event.general_note == "Strict Context Test"
        
        # Verify contextual data injected automatically by the background thread
        assert decoded_event.caller_class == "DummyTelemetryCaller"
        assert decoded_event.caller_function == "execute_telemetry"
        assert decoded_event.logger_name == "TEST_TELEMETRY"
        assert "test_telemetry.py" in decoded_event.caller_file
        assert decoded_event.lineno > 0

def test_telemetry_concurrency_lossless(tmp_path):
    settings = EventSettings(
        name="TEST_CONCURRENCY",
        logs_base_dir=str(tmp_path),
        file_size=1024*1024*10 # 10MB to avoid rollover during test
    )
    telemetry = TelemetryLog(settings)
    
    # Flood the queue with 1000 events
    for i in range(1000):
        event = main_data_pb2.Event()
        event.general_note = f"Event {i}"
        telemetry.send(event)
        

    # Wait for the queue to flush
    telemetry._TelemetryLog__event_writer.queue.join()
    time.sleep(0.1)
    
    event_files = list((tmp_path / "events").glob("events_TEST_CONCURRENCY.log"))
    assert len(event_files) == 1
    
    count = 0
    with open(event_files[0], "rb") as f:
        while True:
            length_bytes = f.read(4)
            if not length_bytes:
                break
            length = struct.unpack(">I", length_bytes)[0]
            f.read(length)
            count += 1
            
    assert count == 1000

def test_telemetry_log_event(tmp_path):
    settings = EventSettings(name=f"TEST_LOG_EVENT_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    # Test setting a standard field
    telemetry.log_event(general_note="Test log_event")
    
    writer = telemetry._TelemetryLog__event_writer
    writer.queue.join()
    time.sleep(0.1)

def test_telemetry_event_context_success(tmp_path):
    settings = EventSettings(name=f"TEST_CTX_SUCCESS_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    with telemetry.event_context(general_note="Context Test"):
        time.sleep(0.05)
        
    writer = telemetry._TelemetryLog__event_writer
    writer.queue.join()
    time.sleep(0.1)

def test_telemetry_event_context_exception(tmp_path):
    settings = EventSettings(name=f"TEST_CTX_FAIL_{tmp_path.name}", logs_base_dir=str(tmp_path))
    telemetry = TelemetryLog(settings)
    
    with pytest.raises(ValueError, match="Test Error"):
        with telemetry.event_context(general_note="Exception Test"):
            raise ValueError("Test Error")
            
    writer = telemetry._TelemetryLog__event_writer
    writer.queue.join()
    time.sleep(0.1)

def test_event_context_default_statuses():
    telemetry_mock = MagicMock()
    
    with EventContext(telemetry_mock, event_type=1, base_kwargs={
        "default_status": registry_pb2.EventStatus.STATUS_COMPLETED,
        "error_status": registry_pb2.EventStatus.STATUS_FAILED
    }) as ctx:
        ctx.attach(some_val=1)
        
    telemetry_mock.log_event.assert_called_once()
    args, kwargs = telemetry_mock.log_event.call_args
    assert kwargs['status'] == registry_pb2.EventStatus.STATUS_COMPLETED
    assert kwargs['some_val'] == 1
    assert "default_status" not in kwargs
    assert "error_status" not in kwargs

def test_event_context_error_statuses():
    telemetry_mock = MagicMock()
    
    try:
        with EventContext(telemetry_mock, event_type=1, base_kwargs={
            "default_status": registry_pb2.EventStatus.STATUS_COMPLETED,
            "error_status": registry_pb2.EventStatus.STATUS_FAILED
        }) as ctx:
            raise ValueError("Test Error")
    except ValueError:
        pass
        
    telemetry_mock.log_event.assert_called_once()
    args, kwargs = telemetry_mock.log_event.call_args
    assert kwargs['status'] == registry_pb2.EventStatus.STATUS_FAILED
