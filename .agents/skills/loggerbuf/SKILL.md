---
name: loggerbuf-guide
description: How to configure and use LoggerBuf for structured telemetry and debugging. Use this skill when asked to integrate telemetry, record structured events, or setup debugging logs.
---

# LoggerBuf Agent Guide

You are integrating or managing `LoggerBuf` in a Python project. `LoggerBuf` is a high-performance structured telemetry and debugging library that uses Protocol Buffers (protobuf) under the hood.

## Core Philosophy
LoggerBuf separates logs into two independent streams:
1. **Telemetry (Binary/Protobuf):** Used for structured business events, analytics, and metrics. These logs are saved in binary format and use strict schemas defined in `main_data.proto`.
2. **Debugger (Text):** Used for standard console output and text logs (INFO, DEBUG, ERROR) meant for humans.

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
This creates the required `loggerbuf_schemas` directory and global configs.

### Complete CLI Command List
* `loggerbuf init`: Initializes the project directory and schemas.
* `loggerbuf build`: Compiles the schema (`main_data.proto`) into Python classes. Run this after ANY modification to the schema.
* `loggerbuf create-event <event_name> --field <name>:<type>`: Creates a new event block. Use `--field` multiple times for non-interactive mode.
* `loggerbuf register-event <field_name> <message_name>`: Registers a new event inside the global `main_data.proto`.
* `loggerbuf add-subfield <message_name> <field_name> <type>`: Adds a new field to an existing event.
* `loggerbuf deprecate-subfield <message_name> <field_name>`: Deprecates an existing field. **GOLDEN RULE:** NEVER delete a field from a proto schema, ALWAYS deprecate it and create a new one.
* `loggerbuf event add-type <event_name>` / `loggerbuf event add-status <event_name>`: Adds standardized Type/Status enums to an event.
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

### 2. Helper Modules (DRY Pattern)
Instead of manually crafting events in every file, you MUST create a central `telemetry_utils.py` file to handle event initialization and avoid repetitive code.

```python
# telemetry_utils.py
from loggerbuf import create_telemetry
from loggerbuf_schemas.main_data_pb2 import Event
from loggerbuf_schemas.usersignup_event_pb2 import UserSignup
from loggerbuf_schemas.registry_pb2 import CounterType

telemetry = create_telemetry()

def log_user_signup(user_id: str, timestamp: int):
    # Initialize the specific event
    signup_event = UserSignup(user_id=user_id, timestamp=timestamp)
    
    # Wrap it in the Event envelope
    main_data = Event()
    main_data.user_signup.CopyFrom(signup_event)
    
    # Send to the telemetry queue
    telemetry.create_event(main_data)

def increment_page_views():
    # Use counters for high-frequency metrics
    telemetry.increment(CounterType.COUNTER_GENERIC, 1)
```

### 3. Missing Information
If the user asks you to implement an event but hasn't provided all the data fields needed for the schema, **STOP and ask the user** what data types and fields are required for the business logic. Don't guess their analytics fields.

## Summary Checklist for Agents
1. Did I check/activate the correct Python environment (e.g., `venv`) if applicable?
2. Did I run `loggerbuf init` if this is a new project?
3. Did I use the CLI to alter the schema?
4. Did I run `loggerbuf build` after changing the schema?
5. Did I use the DRY pattern (helper functions) for Python implementation?
6. Did I deprecate instead of deleting fields?
