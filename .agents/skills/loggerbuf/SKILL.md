---
name: loggerbuf-guide
description: How to configure and use LoggerBuf for structured telemetry and debugging. Use this skill when asked to integrate telemetry, record structured events, or setup debugging logs.
---

# LoggerBuf Agent Guide

You are integrating or managing `LoggerBuf` in a Python project. `LoggerBuf` is a high-performance structured telemetry and debugging library that uses Protocol Buffers (protobuf) under the hood.

## Core Philosophy
LoggerBuf separates logs into independent streams:
1. **Telemetry Events (Binary/Protobuf):** Used for structured business events and analytics. These are highly detailed and saved in binary format using strict schemas.
2. **Telemetry Counters:** A subset of telemetry used for high-frequency, low-cardinality metrics (e.g., counting page views, errors) where full event payloads are too heavy.
3. **Debugger (Text):** Used for standard console output and text logs (INFO, DEBUG, ERROR) meant for humans.

### Event Design Guidelines
When creating a new event schema, encourage robust metadata collection. A good telemetry event should capture context, not just the action. Always consider adding fields for:
* **Identity:** `user_id`, `session_id`, `device_id`
* **Context:** `ip_address`, `user_agent`, `app_version`
* **State:** `status` (enum), `duration_ms` (int64), `error_code` (string)
* **Temporal:** `timestamp` (int64) 
(Note: Only add fields that make sense for the specific business logic, but err on the side of comprehensive analytics).

## Custom Event Types, Statuses, and Counters
In LoggerBuf, `EventType`, `EventStatus`, and `CounterType` are defined in `registry.proto`.
To keep the registry clean, values are assigned in **blocks or ranges**.

- **EventStatus:** Represents the state of an event (e.g., PENDING, COMPLETED, FAILED).
  - General statuses usually span the `0-50` range.
  - Specific custom events should be assigned dedicated ranges (e.g., `51-100`, `101-150`) to avoid overlap.
- **EventType:** Represents what happened (e.g., USER_SIGNUP, API_REQUEST).
  - Generic events usually span `0-100`.
  - Specific domains should be assigned ranges (e.g., `101-200`, `201-300`).
- **CounterType:** Represents metric counters.

**Agent Rule for Custom Types:** If the user asks to create a new custom event, status, or counter, **DO NOT assume the range or limits**. Ask the user what block of numbers (range) should be reserved for this specific domain. Explain to the user that reserving blocks keeps the `registry.proto` organized.

## CLI Usage (Schema Management)
**CRITICAL:** NEVER edit the `.proto` files manually. ALWAYS use the `loggerbuf` CLI within the virtual environment.

Before running any CLI command, ensure you are operating in the correct Python environment. If the project uses a virtual environment (like `venv/` or `.venv/`), activate it first:
```bash
# Example for standard venv (adapt if using Poetry, Conda, or global/container envs)
source venv/bin/activate
```

If you need to explore arguments for a command, use `--help` (e.g., `loggerbuf create-event --help`).

### Project Setup
If setting up LoggerBuf for the first time in a new project, you MUST initialize it:
```bash
loggerbuf init
```
By default, this creates a clean schema environment without demo events. If you want to include the demo event configuration for testing or learning, run:
```bash
loggerbuf init --demo
```
This creates the required `loggerbuf_schemas` directory and global configs.

### Complete CLI Command List
* `loggerbuf init [--demo]`: Initializes the project directory and schemas. Use `--demo` to include demo events.
* `loggerbuf build`: Compiles the schema (`main_data.proto`) into Python classes. Run this after ANY modification to the schema.
* `loggerbuf create-event <event_name> --field <name>:<type>`: Creates a new event block. Use `--field` multiple times for non-interactive mode.
* `loggerbuf register-event <field_name> <message_name>`: Registers a new event inside the global `main_data.proto`.
* `loggerbuf add-subfield <message_name> <field_name> <type>`: Adds a new field to an existing event.
* `loggerbuf deprecate-subfield <message_name> <field_name>`: Deprecates an existing field. **GOLDEN RULE:** NEVER delete a field from a proto schema, ALWAYS deprecate it and create a new one.
* `loggerbuf event add-type <event_name>` / `loggerbuf event add-status <event_name>`: Adds standardized Type/Status enums to an event (respecting range blocks).
* `loggerbuf counter add-type <name>`: Adds a new counter block for high-frequency metrics.
* `loggerbuf decode <file.bin>`: Decodes a binary telemetry log file to standard output (JSON-like).
* `loggerbuf decode-debug <file.log>`: Interactively decodes specific lines from a text debug log.
* `loggerbuf stress-test`: Runs a concurrency benchmark.
* `loggerbuf config init`: Generates a `loggerbuf.json` configuration file (already done if you used `loggerbuf init`).

## Python Implementation Best Practices

### 1. Initialization
LoggerBuf exposes factories for initialization:

```python
from loggerbuf import create_telemetry, create_debugger
from loggerbuf import LogDestination

# Zero-config (recommended for quickstarts)
telemetry = create_telemetry()
debugger = create_debugger()

# Advanced config (custom paths)
telemetry = create_telemetry(name="MAIN", logs_base_dir="/custom/telemetry")
debugger = create_debugger(name="MAIN", logs_base_dir="/custom/debug", stream=LogDestination.CONSOLE_AND_FILE_HISTORY)
```

**Note on Configuration (`loggerbuf.json`):**
If you need to adjust global behaviors (like turning off console colors, changing log rotation thresholds, max file sizes, or default paths), DO NOT try to pass them all via code. Instead, modify the `loggerbuf.json` file that is created in the project root after running `loggerbuf init`. This file contains all the available parameters to tweak the library's behavior.

### 2. Ways to Log (The DRY Pattern)
There are three ways to log events. Always prefer `log_event` or `event_context` over manual building for better Developer Experience.

#### Way 1: Using `log_event` (Recommended for single actions)
Allows passing metadata directly as kwargs. If using sub-events, instantiate the sub-event first and pass it as a kwarg matching its field name in `main_data.proto`.
```python
from loggerbuf import schema_loader

registry_pb2 = schema_loader.get_registry_pb2()
demo_pb2 = schema_loader.get_module("demouserevent_event_pb2")

# Initialize the sub-event for custom data
user_event = demo_pb2.DemoUserEvent(
    name="Process1", 
    counter=42
)

# Pass it along with standard main event fields
telemetry.log_event(
    event_type=registry_pb2.EventType.EVENT_MAIN,
    status=registry_pb2.EventStatus.STATUS_COMPLETED,
    general_note="Process finished successfully",
    user_event=user_event  # Sub-event kwarg!
)
```

#### Way 2: Using `event_context` (Recommended for tracking blocks/duration)
Use the context manager (`with`) to wrap a block of code. It automatically calculates `duration_ms` and traps unhandled exceptions (changing status to `STATUS_ERROR`).
```python
with telemetry.event_context(
    event_type=registry_pb2.EventType.EVENT_MAIN, 
    general_note="Running heavy process",
    user_event=demo_pb2.DemoUserEvent(name="HeavyTask")
) as ctx:
    # Do some work...
    # The event is automatically dispatched when exiting the block!
    pass
```

#### Way 3: Manual Building (Legacy / Complex manipulation)
Only use this if you need complex mutations across multiple functions before dispatching.
```python
main_data_pb2 = schema_loader.get_main_data_pb2()

main_data = main_data_pb2.Event()
main_data.event_type = registry_pb2.EventType.EVENT_MAIN
main_data.user_event.CopyFrom(demo_pb2.DemoUserEvent(name="Manual"))
telemetry.create_event(main_data)
```

#### Way 4: Incrementing Counters
Counters are extremely lightweight and should be used for high-frequency events.
```python
def increment_page_views():
    # Use counters for high-frequency metrics
    telemetry.increment(registry_pb2.CounterType.COUNTER_GENERIC, 1)
```

### 3. Missing Information
If the user asks you to implement an event but hasn't provided all the data fields needed for the schema, **STOP and ask the user** what data types and fields are required for the business logic. Don't guess their analytics fields.

## Summary Checklist for Agents
1. Did I check/activate the correct Python environment (e.g., `venv`) if applicable?
2. Did I run `loggerbuf init` if this is a new project?
3. Did I use the CLI to alter the schema?
4. Did I run `loggerbuf build` after changing the schema?
5. Did I ask the user for range blocks before creating custom Statuses/Types/Counters?
6. Did I use the DRY pattern (`log_event` / `event_context`) for Python implementation?
7. Did I deprecate instead of deleting fields?
