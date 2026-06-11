# LoggerBuf 🚀

🇺🇸 English | 🇪🇸 [Español](README.es.md)

### *Structured Telemetry & High-Performance Async Logger for Python*

`LoggerBuf` is a high-performance, hybrid logging library designed to solve a classic problem: **the clean separation between operational diagnostic logs (debug) and structured business telemetry events**.

Unlike traditional plain-text logging systems, `LoggerBuf` uses **Protocol Buffers (Protobuf)** to guarantee stable and compact data schemas in its telemetry channel. Information is stored in optimized binary files with automatic background rotation and Gzip compression, never interfering with the main application's performance.

---

## 🌟 Key Features & Benefits

*   **⚡ High-Speed Decoupled Concurrency**: Implements the *Producer-Consumer* pattern using a bounded memory queue and a dedicated background thread. Your main application threads enqueue logs and return in microseconds (average **0.004 ms**), completely absorbing disk write latency.
*   **🛡️ Guaranteed Stability (Flat Thread Pool)**: Maintains strict control of exactly one worker thread for physical writing per channel, protecting the OS against Thread Exhaustion.
*   **📦 Compact Binary Telemetry (Length-Prefixed)**: Telemetry events are recorded on disk in pure binary format, occupying a fraction of the space of traditional JSON and avoiding corruption risks.
*   **🛡️ Automated Schema Safety (Linter)**: Includes a built-in schema validator that prevents accidental destructive changes to your historical binary logs.
*   **🔧 Professional CLI**: A powerful, Click-based Command Line Interface (`loggerbuf`) to manage schemas, decode logs, and stress-test the system.

---

## 🚀 Quick Start

### 1. Installation
To install LoggerBuf and its CLI tools globally (or in your virtual environment):
```bash
pip install -e .
```

### 2. The LoggerBuf CLI: Your New Superpower
The CLI is the **first-class citizen** for interacting with LoggerBuf. It automates code generation, prevents manual errors, and decodes your binary telemetry.

| Command | Description |
|---|---|
| `loggerbuf init` | Initializes the `data_logs/protos` directory and the schema registry. |
| `loggerbuf create-event <Name>` | Scaffolds a new `.proto` file for a custom event. |
| `loggerbuf register-event <Name>`| Links your custom event into the `main_data.proto` pipeline. |
| `loggerbuf add-subfield ...` | Safely injects a new field into an existing event. |
| `loggerbuf deprecate-subfield` | Safely deprecates a field without breaking backward compatibility. |
| `loggerbuf build` | Runs the Schema Linter and compiles all `.proto` files into Python classes. |
| `loggerbuf decode-logs <File>` | Decodes binary `.log` files to terminal (pretty) or JSONL. |

> [!TIP]
> Always run `loggerbuf --help` or `loggerbuf <command> --help` for detailed usage instructions.

### 3. Emitting Logs in Python

```python
import loggerbuf
from data_logs import main_data_pb2, event_status_pb2

# 1. Operational Diagnostic Logging
log = loggerbuf.create_debugger(name="MAIN_APP")
log.info("Processing user payment...")
log.error("Transaction failed!")

# 2. Analytical Event Logging (Telemetry)
telemetry = loggerbuf.create_telemetry()

event = main_data_pb2.Event()
event.event_type = event_status_pb2.EventTypes.EVENT_DATA_BASE_PROCESSING
event.general_note = "User successfully registered"

# Instant non-blocking enqueue
telemetry.send(event)
```

---

## 🛡️ Schema Evolution & Safety (The Golden Rules)

Because LoggerBuf stores telemetry in **binary Protobuf format**, modifying a schema incorrectly can permanently corrupt your ability to read historical data.

To prevent this, `loggerbuf build` executes a **Schema Linter** that compares your current `.proto` files against a historical snapshot (`.loggerbuf_schema_snapshot.json`). 

> [!IMPORTANT]
> **The Golden Rule:** Never delete a field, change its data type, or alter its Tag ID (e.g., `= 1;`).

If you need to "modify" a field, you must **deprecate the old one and create a new one**. The CLI automates this safely:

```bash
# 1. Deprecate the old field (keeps historical data readable)
loggerbuf deprecate-subfield UserEvent "age"

# 2. Add the new field (CLI automatically calculates the next available Tag ID)
loggerbuf add-subfield UserEvent "age_str" "string"

# 3. Rebuild
loggerbuf build
```

---

## 🧠 Under the Hood: The "Giant Proto" Myth

You might notice that `main_data.proto` acts as a giant wrapper containing *every single event* your system can emit. 

**Does this mean every log entry is massive?**
No! Protobuf is extremely efficient. Unpopulated fields (fields you don't explicitly set in Python) take up **zero bytes** on disk. 
Even if your `main_data.proto` has 500 different events registered, a serialized log entry will only consume the exact bytes of the 1 event you actually populated. This allows LoggerBuf to be infinitely scalable without wasting disk space.

---

## 🛠️ Configuration (`settings_globals.py`)

You can customize the physical characteristics of the logger and buffers:

```python
# Telemetry Configuration
EVENT_BASE_DIR = "events"          # Root folder for binary events
EVENT_FILE_SIZE = 52428800         # Max size per event file (50 MB)
EVENT_QUEUE_MAX_SIZE = 20000       # Maximum memory buffer capacity
EVENT_QUEUE_STRATEGY = "lossless"  # Overflow: 'lossless' (block to prevent data loss)
```
