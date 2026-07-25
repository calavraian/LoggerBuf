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
  - General statuses span the `0-50` range. **NEVER modify or remove the core generic statuses (0-50)**.
  - Specific custom events should be assigned dedicated ranges (e.g., `51-100`, `101-150`) to avoid overlap.
- **EventType:** Represents what happened (e.g., USER_SIGNUP, API_REQUEST).
  - Generic events span `0-100`. **NEVER modify or remove the core generic event types (0-100)**.
  - Specific domains should be assigned ranges (e.g., `101-200`, `201-300`).
- **CounterType:** Represents metric counters.

**Agent Rule for Custom Types:** If the user asks to create a new custom event, status, or counter, **DO NOT assume the range or limits**. Ask the user what block of numbers (range) should be reserved for this specific domain. Explain to the user that reserving blocks keeps the `registry.proto` organized.

**CRITICAL FORMATTING RULE FOR REGISTRY.PROTO:** When adding a new block to `registry.proto` (even if done manually), you MUST include standard documentation comments describing the block, its range, and the next available value. Example:
```proto
    // User Authentication Events
    // Range: 101-200
    // Next value: 104
    EVENT_AUTH_LOGIN = 101;
    EVENT_AUTH_LOGOUT = 102;
    EVENT_AUTH_PASSWORD_RESET = 103;
```
Failure to include `// Range:` and `// Next value:` will break the structural integrity of the registry.

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
* `loggerbuf --version`: Displays the installed version of LoggerBuf.
* `loggerbuf init [--demo]`: Initializes the project directory and schemas. Use `--demo` to include demo events.
* `loggerbuf build`: Compiles the schema (`main_data.proto`) into Python classes. Run this after ANY modification to the schema.
* `loggerbuf create-event <event_name> --field <name>:<type>`: Creates a new event block. Use `--field` multiple times for non-interactive mode.
* `loggerbuf register-event <field_name> <message_name>`: Registers a new event inside the global `main_data.proto`.
* `loggerbuf add-subfield <message_name> <field_name> <type>`: Adds a new field to an existing event.
* `loggerbuf deprecate-subfield <message_name> <field_name>`: Deprecates an existing field. **GOLDEN RULE:** NEVER delete a field from a proto schema, ALWAYS deprecate it and create a new one.
* `loggerbuf event add-type <event_name> [--reserve X]`: Adds a new type and standard statuses. The `--reserve` flag defines the **total** size of the block, including the items specified in the command (e.g. `--reserve 50` creates a block of 50 total slots). Note: You must run `loggerbuf build` afterwards for the changes to apply. Note: When defining statuses, use pure names (e.g. `SUCCESS`); the CLI automatically prepends the `STATUS_` prefix for you.
* `loggerbuf event add-status <event_name> <status_name>`: Adds a standardized Status enum to an event block. (Note: You must run `loggerbuf build` afterwards for the changes to apply). **IMPORTANT**: If this command fails with a `ValueError` indicating that the reserved range is full, you MUST create a new block (e.g. `EVENT_NAME_PART_2`) or, only if you are absolutely sure it is safe and there are no overlapping blocks below it, manually expand the `Range: X-Y` upper limit in `registry.proto`. Note: Do not prefix the status name with `STATUS_` (e.g. use `SUCCESS` instead of `STATUS_SUCCESS`); the CLI handles prefixing.
* `loggerbuf counter add-type <name> [--reserve X]`: Adds a new counter block for high-frequency metrics.
* `loggerbuf decode <file.bin> [--verify]`: Decodes a binary telemetry log file to standard output (JSON-like). Use `--verify` for interactive secure HMAC verification, or `--verify "KEY"` for explicit verification.
* `loggerbuf decode-debug <file.log>`: Interactively decodes specific lines from a text debug log (supports `--grep`, `--head`, `--tail`, `--format [visual|jsonl|pretty]`, `--output <file>`).
* `loggerbuf filter status|add|remove|reset`: Manages dynamic filters for classes, levels, and metadata fields without needing to restart the application (hot-reloaded).
* `loggerbuf stress-test`: Runs a concurrency benchmark.
* `loggerbuf agents sync`: Downloads or updates the official LoggerBuf agent SKILL.md without recompiling schemas.
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

### 2. Importing Schemas
**CRITICAL:** The `loggerbuf build` command automatically generates a Python facade in the schemas directory (by default `loggerbuf_schemas/__init__.py`).
You must ALWAYS import your events, statuses, and types directly from this facade. NEVER use `schema_loader` in the user's application code (it is meant for internal library use).

```python
# Correct way to get schemas in the user's project
from loggerbuf_schemas import EventType, EventStatus, Event, CounterType
from loggerbuf_schemas import DemoUserEvent # For sub-events
```

**FALLBACK:** Only in extreme cases where the `loggerbuf_schemas/__init__.py` facade is broken or unavailable, you may fallback to importing directly from the raw `_pb2` files as a last resort:
```python
# Fallback ONLY
from loggerbuf_schemas.demouserevent_event_pb2 import DemoUserEvent
```

### 3. Ways to Log (The DRY Pattern)
There are three ways to log events. You **MUST** prefer `log_event` or `event_context` over manual building to keep the code clean and maintainable. Use the manual building approach ONLY if there is a strict technical limitation preventing the use of the facades.

#### Way 1: Using `log_event` (Recommended for single actions)
Allows passing metadata directly as kwargs. If using sub-events, instantiate the sub-event first and pass it as a kwarg matching its field name in `main_data.proto`.
```python
from loggerbuf_schemas import EventType, EventStatus, DemoUserEvent

# Initialize the sub-event for custom data
user_event = DemoUserEvent(
    name="Process1", 
    counter=42
)

# Pass it along with standard main event fields
telemetry.log_event(
    event_type=EventType.EVENT_MAIN,
    status=EventStatus.STATUS_COMPLETED,
    general_note="Process finished successfully",
    user_event=user_event  # Sub-event kwarg!
)
```

#### Way 2: Using `event_context` (Recommended for tracking blocks/duration)
Use the context manager (`with`) to wrap a block of code. It automatically calculates `duration_ms` and traps unhandled exceptions (changing status to `STATUS_ERROR`).

**CRITICAL NOTE FOR SUB-EVENTS:** LoggerBuf DOES NOT use a `oneof` wrapper for custom events. The CLI directly adds new fields to the `Event` message (e.g. `user_command`, `scryfall_query`).
Therefore, you must pass the sub-event as a kwarg matching its exact field name (e.g., `user_command=uc`). 
If you need to mutate the sub-event *during* the context block, keep a reference to the sub-event object rather than trying to extract it from the context manager (`ctx`).

```python
from loggerbuf_schemas import EventType, DemoUserEvent, EventStatus

# 1. Instantiate the sub-event BEFORE the context block
user_event = DemoUserEvent(name="HeavyTask")

# 2. Pass it with its exact field name
# You can optionally specify custom default_status and error_status
with telemetry.event_context(
    event_type=EventType.EVENT_MAIN, 
    general_note="Running heavy process",
    user_event=user_event,
    default_status=EventStatus.STATUS_COMPLETED,
    error_status=EventStatus.STATUS_FAILED
) as ctx:
    # 3. Mutate the object directly via your local reference
    user_event.counter = 100
    
    # The event (with updated counter) is automatically dispatched when exiting!
```

#### Way 3: Manual Building (Legacy / Complex manipulation)
**AVOID IF POSSIBLE.** Only use this if you need complex mutations across multiple functions before dispatching (e.g. passing the `Event` object around). Do NOT use this as your default approach.
```python
from loggerbuf_schemas import Event, EventType, DemoUserEvent

main_data = Event()
main_data.event_type = EventType.EVENT_MAIN
main_data.user_event.CopyFrom(DemoUserEvent(name="Manual"))
telemetry.create_event(main_data)
```

#### Way 4: Incrementing Counters
Counters are extremely lightweight and should be used for high-frequency events.
```python
from loggerbuf_schemas import CounterType

def increment_page_views():
    # Use counters for high-frequency metrics
    telemetry.increment(CounterType.COUNTER_GENERIC, 1)
```

## Advanced Architecture (AI Knowledge)

### Strict Event Structure (No Hallucinations)
LoggerBuf uses Protocol Buffers to strictly enforce schemas. You must NEVER invent or "hallucinate" kwargs when creating an event (e.g., in `telemetry.log_event` or `telemetry.event_context`) if those fields are not explicitly defined in the Protobuf schema. Unsupported kwargs will be safely ignored, but they indicate a flawed understanding of the data model. Stick only to the fields you have registered and the built-in metadata fields.

### Internal Control Footprints & Snapshots
LoggerBuf maintains internal control files (such as `.loggerbuf_schema_snapshot.json` and `.loggerbuf_registry.json`) to orchestrate telemetry generation and track hashes/states. **NEVER manually edit these internal control `.json` snapshots.**
While you *should* use the provided CLI commands (`loggerbuf register-event`, `loggerbuf add-status`, etc.) to modify the system schemas, you MAY manually edit the `.proto` files (like `registry.proto` or `main_data.proto`) as a last resort if the CLI is failing, provided you are extremely careful with the Protobuf syntax. However, the JSON snapshots are strictly off-limits. If editing `registry.proto`, **NEVER modify the core system blocks (EventStatus 0-50, EventType 0-100)** as they are essential for LoggerBuf's internal functioning.

### EventContext Exception Handling
The `event_context` intercepts unhandled exceptions during the `with` block. By default, it uses `STATUS_FAILED` and embeds the error string into `general_note`. If you want to use a specific error status, you can pass `error_status` during initialization.

### Fallback Import Logic
**FALLBACK:** Only in extreme cases where the `loggerbuf_schemas/__init__.py` facade is broken or unavailable, you may fallback (as a last resort) to importing directly from the raw `_pb2` files (e.g. `from loggerbuf_schemas.demouserevent_event_pb2 import DemoUserEvent`).

### 4. Missing Information
If the user asks you to implement an event but hasn't provided all the data fields needed for the schema, **STOP and ask the user** what data types and fields are required for the business logic. Don't guess their analytics fields.

## Summary Checklist for Agents
1. Did I check/activate the correct Python environment (e.g., `venv`) if applicable?
2. Did I run `loggerbuf init` if this is a new project?
3. Did I use the CLI to alter the schema?
4. Did I run `loggerbuf build` after changing the schema?
5. Did I ask the user for range blocks before creating custom Statuses/Types/Counters?
6. Did I import classes/enums directly from `loggerbuf_schemas` instead of using `_pb2` files?
7. Did I use the DRY pattern (`log_event` / `event_context`) for Python implementation?
8. Did I deprecate instead of deleting fields?
