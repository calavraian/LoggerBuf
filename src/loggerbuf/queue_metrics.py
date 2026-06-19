import threading
import datetime
import time
import json
import csv
import io
from enum import Enum

class MetricField(Enum):
    REPORT_GENERATED_AT = ("report_generated_at", "Report Generated At", "Timestamp when this report was created")
    METRICS_START_TIME = ("metrics_start_time", "Metrics Start Time", "Timestamp when the telemetry service began")
    UPTIME = ("uptime_seconds", "Uptime (s)", "Total seconds since the telemetry service started")
    CURRENT_QUEUE_SIZE = ("current_queue_size", "Current Queue Size", "Number of events currently waiting in the queue")
    TOTAL_QUEUED = ("total_queued", "Total Queued", "Cumulative number of events added to the queue")
    TOTAL_PROCESSED = ("total_processed", "Total Processed", "Cumulative number of events successfully written to disk")
    TOTAL_DROPS = ("total_drops", "Total Drops", "Cumulative number of events dropped due to full queue (lossy strategy)")
    PEAK_SIZE = ("peak_size", "Peak Queue Size", "Maximum number of events in the queue at any given time")
    EMPTY_COUNT = ("empty_count", "Queue Empty Count", "Number of times the queue was completely drained")
    AVG_WRITE_TIME = ("avg_write_time_ms", "Average Write Time (ms)", "Average time taken to write a single event to disk")
    MIN_WRITE_TIME = ("min_write_time_ms", "Min Write Time (ms)", "Fastest time taken to write a single event to disk")
    MAX_WRITE_TIME = ("max_write_time_ms", "Max Write Time (ms)", "Slowest time taken to write a single event to disk")
    TOTAL_DRAIN_TIME = ("total_drain_time_s", "Total Drain Time (s)", "Total accumulated time spent draining the queue")
    AVG_DRAIN_TIME = ("avg_drain_time_s", "Average Drain Time (s)", "Average time taken to completely drain the queue")
    MIN_DRAIN_TIME = ("min_drain_time_s", "Min Drain Time (s)", "Fastest time taken to completely drain the queue")
    MAX_DRAIN_TIME = ("max_drain_time_s", "Max Drain Time (s)", "Slowest time taken to completely drain the queue")
    LIFETIME_THROUGHPUT = ("lifetime_throughput_eps", "Lifetime Throughput (EPS)", "Average events processed per second over the entire uptime")
    PEAK_CAPACITY = ("peak_capacity_eps", "Peak Capacity (EPS)", "Theoretical maximum events per second based on current write speeds")

    @property
    def key(self):
        return self.value[0]
        
    @property
    def display_name(self):
        return self.value[1]
        
    @property
    def description(self):
        return self.value[2]


class QueueMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.metrics_start_time = datetime.datetime.now().isoformat()
        self.peak_size = 0
        self.total_queued = 0
        self.total_processed = 0
        self.total_drops = 0
        self.empty_count = 0
        self.total_write_time = 0.0
        self.min_write_time = float('inf')
        self.max_write_time = 0.0
        self.drain_start_time = None
        self.total_drain_time = 0.0
        self.min_drain_time = float('inf')
        self.max_drain_time = 0.0

    def record_enqueue(self, current_qsize):
        with self.lock:
            self.total_queued += 1
            actual_size = current_qsize + 1
            if actual_size > self.peak_size:
                self.peak_size = actual_size
            if actual_size == 1 and self.drain_start_time is None:
                self.drain_start_time = time.perf_counter()

    def record_dequeue(self, write_duration, current_qsize):
        with self.lock:
            self.total_processed += 1
            self.total_write_time += write_duration
            if write_duration < self.min_write_time:
                self.min_write_time = write_duration
            if write_duration > self.max_write_time:
                self.max_write_time = write_duration
                
            if current_qsize == 0:
                self.empty_count += 1
                if self.drain_start_time is not None:
                    duration = time.perf_counter() - self.drain_start_time
                    self.total_drain_time += duration
                    if duration < self.min_drain_time:
                        self.min_drain_time = duration
                    if duration > self.max_drain_time:
                        self.max_drain_time = duration
                    self.drain_start_time = None

    def record_drop(self):
        with self.lock:
            self.total_drops += 1

    def get_report(self, current_qsize=0, keys: list = None, output_format: str = "dict", verbose: bool = False):
        with self.lock:
            now = datetime.datetime.now()
            start_dt = datetime.datetime.fromisoformat(self.metrics_start_time)
            uptime_seconds = (now - start_dt).total_seconds()
            
            avg_write = (self.total_write_time / self.total_processed) if self.total_processed > 0 else 0.0
            avg_write_ms = avg_write * 1000.0
            min_write_ms = (self.min_write_time * 1000) if self.min_write_time != float('inf') else 0.0
            max_write_ms = (self.max_write_time * 1000)
            
            avg_drain = (self.total_drain_time / self.empty_count) if self.empty_count > 0 else 0.0
            min_drain = self.min_drain_time if self.min_drain_time != float('inf') else 0.0
            max_drain = self.max_drain_time
            
            lifetime_throughput_eps = (self.total_processed / uptime_seconds) if uptime_seconds > 0 else 0.0
            peak_capacity_eps = (1.0 / avg_write) if avg_write > 0 else 0.0
            
            raw_data = {
                MetricField.REPORT_GENERATED_AT: now.isoformat(),
                MetricField.METRICS_START_TIME: self.metrics_start_time,
                MetricField.UPTIME: uptime_seconds,
                MetricField.CURRENT_QUEUE_SIZE: current_qsize,
                MetricField.TOTAL_QUEUED: self.total_queued,
                MetricField.TOTAL_PROCESSED: self.total_processed,
                MetricField.TOTAL_DROPS: self.total_drops,
                MetricField.PEAK_SIZE: self.peak_size,
                MetricField.EMPTY_COUNT: self.empty_count,
                MetricField.AVG_WRITE_TIME: avg_write_ms,
                MetricField.MIN_WRITE_TIME: min_write_ms,
                MetricField.MAX_WRITE_TIME: max_write_ms,
                MetricField.TOTAL_DRAIN_TIME: self.total_drain_time,
                MetricField.AVG_DRAIN_TIME: avg_drain,
                MetricField.MIN_DRAIN_TIME: min_drain,
                MetricField.MAX_DRAIN_TIME: max_drain,
                MetricField.LIFETIME_THROUGHPUT: lifetime_throughput_eps,
                MetricField.PEAK_CAPACITY: peak_capacity_eps
            }
            
            if keys:
                # Filter by checking if the enum is in the list of enums provided
                raw_data = {k: raw_data[k] for k in keys if k in raw_data}
                
            report = {}
            for field_enum, value in raw_data.items():
                if verbose:
                    report[field_enum.key] = {
                        "display_name": field_enum.display_name,
                        "value": value,
                        "description": field_enum.description
                    }
                else:
                    report[field_enum.key] = value
                
            if output_format == "json":
                return json.dumps(report, indent=4)
            elif output_format == "string":
                if verbose:
                    lines = []
                    for field_enum, value in raw_data.items():
                        lines.append(f"[{field_enum.display_name}]")
                        lines.append(f"  Valor: {value}")
                        lines.append(f"  Info:  {field_enum.description}\n")
                    return "\n".join(lines).strip()
                else:
                    return "\n".join([f"{k}: {v}" for k, v in report.items()])
            elif output_format == "csv":
                output = io.StringIO()
                if verbose:
                    writer = csv.writer(output)
                    writer.writerow(["Key", "Display Name", "Value", "Description"])
                    for field_enum, value in raw_data.items():
                        writer.writerow([field_enum.key, field_enum.display_name, value, field_enum.description])
                else:
                    writer = csv.DictWriter(output, fieldnames=report.keys())
                    writer.writeheader()
                    writer.writerow(report)
                return output.getvalue()
                
            return report
