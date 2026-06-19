import pytest
import time
import json
import csv
import io
from loggerbuf.queue_metrics import QueueMetrics, MetricField

def test_queue_metrics_initialization():
    metrics = QueueMetrics()
    assert metrics.total_queued == 0
    assert metrics.total_processed == 0
    assert metrics.peak_size == 0
    assert metrics.total_drops == 0
    assert metrics.min_write_time == float('inf')

def test_record_enqueue():
    metrics = QueueMetrics()
    metrics.record_enqueue(0)
    assert metrics.total_queued == 1
    assert metrics.peak_size == 1
    
    metrics.record_enqueue(1)
    assert metrics.total_queued == 2
    assert metrics.peak_size == 2

def test_record_dequeue_and_drain():
    metrics = QueueMetrics()
    metrics.record_enqueue(0)
    
    # Simulate a write duration of 0.1s
    metrics.record_dequeue(0.1, 0)
    assert metrics.total_processed == 1
    assert metrics.empty_count == 1
    assert metrics.min_write_time == 0.1
    assert metrics.max_write_time == 0.1
    
def test_record_drop():
    metrics = QueueMetrics()
    metrics.record_drop()
    assert metrics.total_drops == 1

def test_get_report_formats():
    metrics = QueueMetrics()
    metrics.record_enqueue(0)
    metrics.record_dequeue(0.05, 0)
    
    # JSON format
    json_report = metrics.get_report(current_qsize=0, output_format="json")
    parsed = json.loads(json_report)
    assert parsed["total_queued"] == 1
    assert parsed["total_processed"] == 1
    
    # String format
    string_report = metrics.get_report(output_format="string")
    assert "total_queued: 1" in string_report
    
    # Verbose string format
    verbose_string_report = metrics.get_report(output_format="string", verbose=True)
    assert "[Total Queued]" in verbose_string_report
    assert "Valor: 1" in verbose_string_report
    
    # CSV format
    csv_report = metrics.get_report(output_format="csv")
    assert "total_queued" in csv_report

def test_get_report_filter_keys():
    metrics = QueueMetrics()
    metrics.record_enqueue(0)
    
    report = metrics.get_report(keys=[MetricField.TOTAL_QUEUED])
    assert "total_queued" in report
    assert "total_processed" not in report
