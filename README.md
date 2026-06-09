# LoggerBuf 🚀

🇺🇸 English | 🇪🇸 [Español](README.es.md)

### *Structured Telemetry & High-Performance Async Logger for Python*

`LoggerBuf` is a high-performance, hybrid logging library designed to solve a classic problem: **the clean separation between operational diagnostic logs (debug) and structured business telemetry events**.

Unlike traditional plain-text logging systems, `LoggerBuf` uses **Protocol Buffers (Protobuf)** to guarantee stable and compact data schemas in its telemetry channel. Information is stored in optimized binary files with automatic background rotation and Gzip compression, never interfering with the main application's performance.

---

## 🌟 Key Features & Benefits

*   **⚡ High-Speed Decoupled Concurrency**: Implements the *Producer-Consumer* pattern using a bounded memory queue and a dedicated background thread (*Daemon Worker Thread*). Your main application threads enqueue logs and return in microseconds (average **0.004 ms**), completely absorbing disk write latency.
*   **🛡️ Guaranteed Stability (Flat Thread Pool)**: No more runaway ad-hoc threads. Whether your app handles 10 or 10,000 concurrent requests, `LoggerBuf` maintains strict control of exactly one worker thread for physical writing per channel, protecting the OS against Thread Exhaustion.
*   **📦 Compact Binary Telemetry (Length-Prefixed)**: Telemetry events are recorded on disk in pure binary format (Length-Prefixed Framing: 4-byte length header + raw Protobuf bytes). This occupies a fraction of the space of traditional JSON and avoids corruption risks from special characters or line breaks (`0x0A`).
*   **⚙️ Configurable Overflow Profiles**:
    *   `LOSSLESS` (Safe Mode - Telemetry): Briefly blocks if the queue is full, ensuring not a single analytics event is lost.
    *   `LOSSY` (Extreme Speed Mode - Debug): Silently discards the oldest operational logs if the disk queue is saturated, shielding your main application's performance.
*   **🔍 Ultra-Fast Native Context**: Captures the exact file, line, function, and class emitting each log at the C-level (using Python's native logging framework), eliminating the costly manual stack walking with `inspect` that slows down applications.
*   **📊 Offline Async Decoder (CLI)**: Includes a powerful CLI tool that automates decompressing, validating, extracting performance metrics, and exporting your binary files to JSON-Lines (JSONL) format—ready for ClickHouse, BigQuery, or ElasticSearch.

---

## 🚀 Quick Start

### 1. Initialization and Basic Import

The API exposes two unified top-level constructors: `create_debugger()` for operational logs and `create_telemetry()` for structured events.

```python
import loggerbuf
from data_logs import main_data_pb2, event_status_pb2

# 1. Get the operational debugger (console + async file)
log = loggerbuf.create_debugger(name="MAIN_APP")
log.info("Starting application...")

# 2. Get the structured telemetry logger
telemetry = loggerbuf.create_telemetry()
```

### 2. Operational Diagnostic Logging (DebuggerLog)
The debugger supports standard logging levels (`debug`, `info`, `warning`, `error`, `critical`).

```python
class PaymentService:
    def process(self):
        log.info("Processing user payment...")
        try:
            # ... business logic ...
            log.debug("Gateway connection established.")
        except Exception as e:
            log.error(f"Transaction failed: {e}")
```
*Automatically formatted output in console and file:*
`[2026-05-29 10:15:30,123] >>MAIN_APP<< (payment.py::PaymentService::process->5) - *INFO* - message::>Processing user payment...`

### 3. Analytical Event Logging (TelemetryLog)
Send your structured **Protobuf** messages directly.

```python
# Create and populate your Protobuf message
event = main_data_pb2.Event()
event.event_type = event_status_pb2.EventTypes.EVENT_DATA_BASE_PROCESSING
event.general_note = "User successfully registered"
event.status = event_status_pb2.Status.STATUS_COMPLETED

# Instant non-blocking enqueue
telemetry.send(event)
```

---

## 📊 CLI Decoder (Offline Ingestion Tool)

Since analytical event files are saved in an extremely compact binary format and automatically rotate into compressed `.gz` files, `LoggerBuf` includes a command-line decoder to process data on demand.

### Quick Stats & Metrics
```bash
python3 -m testlogger.decoder --input events/history/2026-05-29/events_MAIN_2026-05-29.log.1.gz --stats
```
*Output:*
```text
=== LoggerBuf Telemetry Statistics ===
File: events/history/2026-05-29/events_MAIN_2026-05-29.log.1.gz
Total events decoded: 1540

Event Types Breakdown:
  - EVENT_DATA_BASE_PROCESSING: 1200
  - EXAMPLE_EVENT_API_INVOKED: 340

Statuses Breakdown:
  - STATUS_COMPLETED: 1200
  - EXAMPLE_EVENT_STATUS_STARTED: 340
```

### Export to JSON-Lines (JSONL) for Databases (ClickHouse, BigQuery, ELK)
```bash
python3 -m testlogger.decoder --input events/events_MAIN.log -o raw_events.jsonl --format jsonl
```

### Extract Subsets of Events (Memory Safe)
Thanks to its asynchronous design using generators and circular buffers, you can inspect immense files (Gigabytes) without collapsing RAM:
```bash
# Extract only the first 100 events
python3 -m testlogger.decoder --input events/events_MAIN.log --head 100

# Extract only the last 50 events (OOM Safe, minimal RAM usage)
python3 -m testlogger.decoder --input events/events_MAIN.log --tail 50
```

---

## 🛠️ Configuration (`settings_globals.py`)

You can customize the physical characteristics of the logger and buffers in `settings_globals.py`:

```python
# Debugger Configuration
LOGGING_BASE_DIR = "logs"          # Root folder for operational logs
LOGGING_FILE_SIZE = 10485760       # Max size per file (10 MB)
LOGGING_BACKUP_COUNT = 5           # Number of historical files to keep
LOGGING_QUEUE_MAX_SIZE = 10000     # Maximum memory buffer capacity
LOGGING_QUEUE_STRATEGY = "lossy"   # Overflow: 'lossy' (discard) or 'lossless' (block)

# Telemetry Configuration
EVENT_BASE_DIR = "events"          # Root folder for binary events
EVENT_FILE_SIZE = 52428800         # Max size per event file (50 MB)
EVENT_QUEUE_MAX_SIZE = 20000       # Maximum memory buffer capacity
EVENT_QUEUE_STRATEGY = "lossless"  # Overflow: 'lossless' (block to prevent data loss)
```

---

## 📈 Performance, Observability & Benchmarks

`LoggerBuf` is not a black box; it includes native support for **Observability** that allows you to extract precise metrics of queue behavior under load in real time. Use the powerful `MetricField` enum to guarantee zero syntax errors and IDE autocomplete:

```python
from testlogger.queue_metrics import MetricField

# Request specific metrics in human-readable verbose string mode
reporte = telemetry.get_metrics(
    keys=[MetricField.TOTAL_DROPS, MetricField.PEAK_CAPACITY],
    output_format="string",
    verbose=True
)
print(reporte)
```
*Output:*
```text
[Total Drops]
  Valor: 0
  Info:  Cumulative number of events dropped due to full queue (lossy strategy)

[Peak Capacity (EPS)]
  Valor: 8093.8
  Info:  Theoretical maximum events per second based on current write speeds
```

### Extreme Concurrency Benchmark Results

In our stress tests (spawning multiple threads writing continuous bursts of thousands of concurrent data points):

*   **Client Thread Performance**: **0.0045 ms (4.5 microseconds)** average per log/event call, allowing your main execution thread to continue at 100% processing speed without blocking.
*   **Resource Stability**: Active process threads remain flat and stable during the burst (exactly 1 background worker thread per disk channel), asynchronously absorbing physical writes without CPU spikes or overloads.
*   **Real Write Speed**: The worker processes and serializes events to physical disk at an average speed of **7,900 events per second**, requiring only **19% of the available queue** during extreme instantaneous bursts.
