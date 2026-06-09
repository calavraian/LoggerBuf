import os
import time
import pytest
from telemetry import TelemetryLog, EventSettings
from data_logs import main_data_pb2, event_status_pb2, event_example_pb2
from settings_globals import QueueStrategy
import struct

class DummyTelemetryCaller:
    def execute_telemetry(self, telemetry_logger):
        event = main_data_pb2.Event()
        event.event_type = event_status_pb2.EventTypes.EVENT_DATA_BASE_PROCESSING
        event.general_note = "Strict Context Test"
        event.status = event_status_pb2.Status.STATUS_COMPLETED
        
        # Nested sub event
        sub_event = event_example_pb2.ExampleSubEvent()
        sub_event.name = "nested_test"
        sub_event.counter = 42
        sub_event.operation_type = event_example_pb2.ExampleSubEvent.OperationType.OPERATION_DATA_WRITE
        
        event.example_sub_event.CopyFrom(sub_event)
        
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
    telemetry._TelemetryLog__writer.queue.join()
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
        
        # Verify custom notes and nested proto
        assert decoded_event.general_note == "Strict Context Test"
        assert decoded_event.example_sub_event.name == "nested_test"
        assert decoded_event.example_sub_event.counter == 42
        assert decoded_event.example_sub_event.operation_type == event_example_pb2.ExampleSubEvent.OperationType.OPERATION_DATA_WRITE
        
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
    telemetry._TelemetryLog__writer.queue.join()
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
