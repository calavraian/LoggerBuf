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


## 🏢 Enterprise Debugging Features

LoggerBuf provides advanced, enterprise-grade features that let you fine-tune the debugger output at runtime, without needing to restart your application or change any code.

### 1. Dynamic Console Filtering
Sometimes you only want to see logs from a specific class or severity level on the console, without stopping the application or affecting the file logs. You can configure this dynamically via `loggerbuf.json`:
- `LOGGING_CONSOLE_ENABLED`: Turn the console output completely on or off (`true`/`false`).
- `LOGGING_CONSOLE_ALLOWED_CLASSES`: List of class names to show on the console (e.g., `["PaymentService", "AuthWorker"]`). Leave empty to allow all.
- `LOGGING_CONSOLE_ALLOWED_LEVELS`: List of log levels to show on the console (e.g., `["ERROR", "CRITICAL"]`). Leave empty to allow all.

### 2. Log Destination & Persistence (History On/Off)
LoggerBuf gives you complete control over where logs are sent. Persistence is intentional, not forced. You can configure `LOGGING_DESTINATION` via `loggerbuf.json` with 5 different modes:
- `CONSOLE`: History OFF. Prints beautifully formatted logs to the terminal only. Perfect for local dev.
- `JSON`: History ON. Writes structured JSON logs to disk. Excellent for log aggregators.
- `GZIP`: History ON. Writes directly to compressed Gzip files. Ideal for production servers with limited storage.
- `JSON_AND_CONSOLE`: History ON. Writes to disk and echoes to the terminal.
- `GZIP_AND_CONSOLE`: History ON. Writes to compressed disk files and echoes to the terminal.
*(If a misconfiguration occurs, LoggerBuf will safely fallback to `CONSOLE` to ensure you never lose a trace).*

### 3. Configurable Metadata
By default, the debugger tracks timestamp, logger name, log level, file name, class, function, and line number. You can customize exactly which metadata fields are included in both the JSON file logs and the console output using the `LOGGING_METADATA` key in your configuration:
```json
"LOGGING_METADATA": ["TIMESTAMP", "LEVEL", "MESSAGE"]
```
This reduces storage costs and visual noise if you don't need full tracking.

### 4. Complex Object Serialization
You can pass dictionaries, lists, or custom class instances directly to the logger. LoggerBuf will safely intercept and serialize them to formatted JSON (with a silent fail-safe if an object is unserializable), keeping your code perfectly clean:
```python
user_data = {"id": 123, "role": "admin"}
log.info(user_data)
```

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

**Understanding the Output Signature:**
The custom formatter instantly reveals the *where* and *what* of any log entry without requiring you to pass extra context. By default, every log line contains:
- `[Timestamp]`: Accurate down to milliseconds.
- `>>LoggerName<<`: Helps isolate which module emitted the log (e.g. `MAIN_APP`, `DB_WORKER`).
- `(filename.py::ClassName::methodName->lineNumber)`: The exact code location. No more guessing where the error originated.
- `- *LEVEL* -`: The severity (`INFO`, `ERROR`, etc.).
- `message::> [Payload]`: The actual log message or serialized JSON object.

### 2. Analytical Event Logging (Telemetry)
Telemetry uses Protobuf. Every event you track should be categorized using your custom `EventType` and `EventStatus` enums to ensure consistency across your organization. Just like the debugger, Telemetry automatically injects creation timestamps and routing headers behind the scenes.

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
| `loggerbuf event add-type <Name>` | Adds a new sub-classification `EventType` to your project. |
| `loggerbuf event add-status <Type> <Status>`| Adds a new `EventStatus` specifically under an `EventType`. |

### Powerful CLI Examples

**1. Decoding Binary Telemetry:**
Extract thousands of binary events into readable JSON for analysis.
```bash
# Output binary telemetry data as human-readable JSON
loggerbuf decode-logs logs/telemetry_queue.bin

# Decode directly to a JSONL file for database ingestion
loggerbuf decode-logs logs/telemetry_queue.bin --out output.jsonl
```

**2. Exploring Debug History:**
Search through gigabytes of Gzip or JSON operational logs effortlessly using our built-in explorer.
```bash
# Search for 'CRITICAL' in a compressed archive and return the last 20 matches
loggerbuf decode-debug logs/history/debug_logs.gz --grep "CRITICAL" --tail 20

# View the first 50 logs of a standard JSON log file
loggerbuf decode-debug logs/history/debug_logs.json --head 50
```

### Sub-classifying Events (EventType & EventStatus)
To achieve granular analytics, LoggerBuf allows you to define a hierarchy of sub-classifications (**EventType**) and their respective states (**EventStatus**). 
**Note:** Using custom types and statuses is completely optional. You can always use the default global statuses (e.g. `STATUS_PENDING`, `STATUS_COMPLETED`) for any event if you prefer simplicity.

```bash
# Add a new EventType for network events, along with two statuses.
loggerbuf event add-type NETWORK --statuses STARTED,FAILED

# Later on, add a new status to the NETWORK type
loggerbuf event add-status NETWORK TIMEOUT

# View your registered types and statuses
loggerbuf event list
```
*Don't forget to run `loggerbuf build` to compile the changes made by these commands!*
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
