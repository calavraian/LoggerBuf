import os
import json
import time
import struct
import pytest
from telemetry import TelemetryLog, EventSettings
import schema_loader
main_data_pb2 = schema_loader.get_main_data_pb2()
from cli.handlers.decode import decode_file
import subprocess
import sys

@pytest.fixture
def sample_telemetry_file(tmp_path):
    test_name = f"TEST_DECODER_{tmp_path.name.replace('-', '_')}"
    settings = EventSettings(
        name=test_name,
        logs_base_dir=str(tmp_path)
    )
    telemetry = TelemetryLog(settings)
    
    # Write 5 events
    for i in range(5):
        event = main_data_pb2.Event()
        event.general_note = f"Decoder Event {i}"
        telemetry.send(event)
        
    telemetry._TelemetryLog__event_writer.queue.join()
    time.sleep(0.1)
    
    events_dir = tmp_path / "events"
    event_files = list(events_dir.glob(f"events_{test_name}.log"))
    assert len(event_files) == 1
    return str(event_files[0])

def test_decoder_yield_vs_list(sample_telemetry_file):
    generator = decode_file(sample_telemetry_file)
    import types
    assert isinstance(generator, types.GeneratorType), "Decoder should yield, not return a list"
    
    events = list(generator)
    assert len(events) == 5
    for i, event in enumerate(events):
        assert event.general_note == f"Decoder Event {i}"

def test_decoder_json_validation(sample_telemetry_file, tmp_path):
    output_file = tmp_path / "output.jsonl"
    
    # Execute CLI
    cmd = [
        sys.executable, "-m", "cli.console", "decode",
        sample_telemetry_file,
        "--output", str(output_file),
        "--format", "jsonl"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert output_file.exists()
    
    content = output_file.read_text().strip().split('\n')
    assert len(content) == 5
    
    for i, line in enumerate(content):
        data = json.loads(line)
        assert data["generalNote"] == f"Decoder Event {i}"

def test_decoder_cli_head_tail(sample_telemetry_file, tmp_path):
    # Head 2
    cmd_head = [
        sys.executable, "-m", "cli.console", "decode",
        sample_telemetry_file,
        "--head", "2",
        "--format", "jsonl"
    ]
    result = subprocess.run(cmd_head, capture_output=True, text=True)
    assert result.returncode == 0
    lines = result.stdout.strip().split('\n')
    assert len(lines) == 2
    assert json.loads(lines[0])["generalNote"] == "Decoder Event 0"
    
    # Tail 2
    cmd_tail = [
        sys.executable, "-m", "cli.console", "decode",
        sample_telemetry_file,
        "--tail", "2",
        "--format", "jsonl"
    ]
    result_tail = subprocess.run(cmd_tail, capture_output=True, text=True)
    assert result_tail.returncode == 0
    lines_tail = result_tail.stdout.strip().split('\n')
    assert len(lines_tail) == 2
    assert json.loads(lines_tail[-1])["generalNote"] == "Decoder Event 4"

def test_decoder_cli_stats(sample_telemetry_file):
    cmd_stats = [
        sys.executable, "-m", "cli.console", "decode",
        sample_telemetry_file,
        "--stats"
    ]
    result = subprocess.run(cmd_stats, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Total events decoded: 5" in result.stdout
