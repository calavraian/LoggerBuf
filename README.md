# LoggerBuf 🚀

🇺🇸 English | 🇪🇸 [Español](README.es.md)

### *Structured Telemetry & High-Performance Async Logger for Python*

`LoggerBuf` is a high-performance, hybrid logging library designed to solve a classic problem: **the clean separation between operational diagnostic logs (debug) and structured business telemetry events**.

Unlike traditional plain-text logging systems that choke under heavy loads and corrupt data, the native implementation of **Protocol Buffers** in `LoggerBuf` guarantees stable, compact, and ultra-fast data schemas. Your information is safely stored in optimized binary files with background automatic rotation and compression, ensuring zero interference with your main application's performance.

---

## 🤔 Why LoggerBuf? (The Problem & The Solution)

**The Problem:** 
Configuring Python's native `logging` module for production is notoriously complex. If you want asynchronous writing, automatic file rotation, and compression, you end up writing hundreds of lines of boilerplate. Worse, developers often mix operational errors ("Failed to connect to DB") with business analytics ("User completed purchase") in the same giant text files, making data extraction a nightmare.

**The Solution:**
`LoggerBuf` solves this by offering a dual-channel architecture that works out of the box, granting you "free" automatic context for superior tracking and debugging:
1.  **Debugger**: For operational logs (human-readable text). It automatically injects the exact file, class, and line number into every log without the slow `inspect` magic.
2.  **Telemetry**: For business analytics. It uses binary Protocol Buffers to ensure your data is always structured, strongly typed, and ready for massive database ingestion.

**The "Superpower" (Zero-Setup):**
With just two lines of code, you get an industrial-grade, non-blocking, auto-rotating logger:

```python
import loggerbuf

# Boom! You now have a fast, async, auto-rotating logger with free context injection.
log = loggerbuf.create_debugger(name="MAIN_APP")
log.info("Application started safely.")
```

---

## ⚙️ Under the Hood (The Technical Engine)

*   **⚡ Async Background Thread**: Enqueuing a log takes an average of **0.004 ms**. A dedicated background worker handles the heavy lifting of writing to disk, ensuring your main application never blocks.
*   **📦 Auto-Rotation & Compression**: Files automatically rotate when they hit a size limit (e.g., 10MB) and historical files are compressed using Gzip in the background to save disk space.
*   **🛡️ Configurable Overflow Profiles**:
    *   `LOSSLESS` (Telemetry): Briefly blocks if the queue is full, ensuring not a single analytics event is lost.
    *   `LOSSY` (Debugger): Silently discards the oldest logs if the disk is saturated, protecting your app's performance during extreme log bursts.

---

## 💻 Operational Guide (In the Trenches)

### 1. Operational Diagnostic Logging (Debugger)
Use the debugger for everyday application monitoring (`debug`, `info`, `warning`, `error`, `critical`). 

```python
class PaymentService:
    def process(self):
        log.info("Processing user payment...")
        try:
            # ... business logic ...
        except Exception as e:
            log.error(f"Transaction failed: {e}")
```
*Notice the "Free Tracking Info" automatically enriched in the output:*
`[2026-05-29 10:15:30,123] >>MAIN_APP<< (payment.py::PaymentService::process->5) - *INFO* - message::>Processing user payment...`

### 2. Analytical Event Logging (Telemetry)
Telemetry uses Protobuf. Every event you track should be categorized using your custom `EventTypes` and `Status` enums to ensure consistency across your organization. Just like the debugger, Telemetry automatically injects creation timestamps and routing headers behind the scenes.

```python
from data_logs import main_data_pb2, event_status_pb2

telemetry = loggerbuf.create_telemetry()

# Create your structured event
event = main_data_pb2.Event()
event.event_type = event_status_pb2.EventTypes.EVENT_DATA_BASE_PROCESSING
event.general_note = "User successfully registered"
event.status = event_status_pb2.Status.STATUS_COMPLETED

# Send it to the async binary queue
telemetry.send(event)
```

---

## 🎛️ Absolute Control (Advanced Configuration)

While the "Zero-Setup" default is great for getting started, advanced developers need absolute control. `LoggerBuf` doesn't lock you in. You can heavily customize rotation sizes, memory queues, and paths globally or per-instance.

**1. Global Defaults (`settings_globals.py`)**
Adjust the engine's core constraints:
```python
LOGGING_FILE_SIZE = 10485760       # Max size per file (10 MB)
LOGGING_QUEUE_MAX_SIZE = 10000     # Memory queue capacity
LOGGING_QUEUE_STRATEGY = "lossy"   # Overflow behavior
```

## ⚙️ Advanced Settings & Hot Reload

LoggerBuf can be globally configured via a `loggerbuf.json` file in your root directory. The easiest way to manage this is via the CLI.

```bash
loggerbuf config set LOGGING_FILE_SIZE 5000000
```

> [!TIP]
> **Zero-Downtime Hot Reload**
> When you change the `LOG_LEVEL` (e.g. `loggerbuf config set LOG_LEVEL DEBUG`), the underlying active LoggerBuf instances detect the change in the JSON file and will dynamically elevate your log level **without needing to restart the application**. Other structural changes (like file size) will require a manual restart.

### Consolidated Telemetry
For maximum I/O efficiency, LoggerBuf uses a single JSON file for all debug output (`debug_logs_MAIN.log`). You can easily explore it via:
```bash
loggerbuf decode-debug logs/history/debug_logs_MAIN.log --grep "Error" --tail 50
```

**2. Instance-Level Overrides**
You can bypass global settings entirely when creating a logger:
```python
# Create a specialized logger that rotates every 50MB and uses a lossless queue
custom_log = loggerbuf.create_debugger(
    name="CRITICAL_WORKER",
    max_bytes=52428800,
    queue_strategy="lossless"
)
```

---

## 🔧 The CLI (Your Administration Tools)

The LoggerBuf CLI (`loggerbuf`) is the **first-class citizen** for managing your telemetry schemas and decoding your binary files.

| Command | Description |
|---|---|
| `loggerbuf init` | Initializes the `data_logs/protos` directory. |
| `loggerbuf create-event <Name>` | Scaffolds a new `.proto` file for a custom event. |
| `loggerbuf register-event <Name>`| Links your custom event into the `main_data.proto` pipeline. |
| `loggerbuf add-subfield ...` | Safely injects a new field into an existing event. |
| `loggerbuf build` | Runs the Schema Linter and compiles `.proto` files to Python. |
| `loggerbuf config set <key> <value>` | Safely updates global settings. Example: `loggerbuf config set LOG_LEVEL DEBUG` |
| `loggerbuf config get <key>` | Retrieves the active value for a configuration key. |
| `loggerbuf decode-logs <File>` | Decodes binary telemetry logs to Terminal or JSONL. |
| `loggerbuf decode-debug <File>` | Explores historical JSON debug logs visually (supports `--grep`, `--head`, `--tail`). |

### 🛡️ Schema Evolution (The Golden Rules)
Because telemetry is stored in binary, **never delete a field or change its data type**. 
`loggerbuf build` includes a **Schema Linter** that compares your files against a historical snapshot and blocks destructive changes. 

If you need to change a field, use the CLI to deprecate the old one and add a new one safely:
```bash
loggerbuf deprecate-subfield UserEvent "age"
loggerbuf add-subfield UserEvent "age_str" "string"
loggerbuf build
```

---

## 🧠 The "Giant Proto" Myth

`main_data.proto` acts as a giant wrapper containing *every single event* your system can emit. 

**Does this mean every log entry is massive? No.**
Protobuf is extremely efficient. Unpopulated fields take up **zero bytes** on disk. Even if your schema has 500 different events, a serialized log entry will only consume the exact bytes of the 1 event you actually populated.
