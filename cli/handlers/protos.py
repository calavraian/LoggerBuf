import os
import re
import subprocess
import glob
from cli.utils import registry
from cli.utils import schema_validator

PROTO_DIR = "data_logs/protos"
MAIN_PROTO = os.path.join(PROTO_DIR, "main_data.proto")

BASE_MAIN_PROTO_TEMPLATE = """syntax = "proto3";

import "event_status.proto";
{imports}

package main_data;

message Event {{
    // The type of event. Add event types in [EventTypes].
    enum_control.EventType event_type = 1;

    // The timestamp of the event is set by the server
    string timestamp = 2;

    // Optional note for the event.
    string general_note = 3;
    
    // The status of the event is set by the app. Update [Status] list.
    enum_control.EventStatus status = 4;

    // The name of the EventLogger instance (e.g. MAIN, SECURITY)
    string logger_name = 6;

    // The file name where the event was generated
    string caller_file = 7;

    // The class name where the event was generated
    string caller_class = 8;

    // The function/method name where the event was generated
    string caller_function = 9;

    // The line number where the event was generated
    int32 lineno = 10;

    // --- DYNAMIC EVENTS ---
{dynamic_fields}
{deprecated_fields}
}}
"""

def init():
    """Initializes the proto structure and registry."""
    os.makedirs(PROTO_DIR, exist_ok=True)
    registry.init_registry()
    build()

def build():
    """Builds the main_data.proto based on registry and calls protoc."""
    data = registry.get_registry()
    events = data.get("events", {})
    
    imports = set()
    active_fields = []
    deprecated_fields = []
    
    # Base compatibility (example_sub_event is 5, normally)
    # If the user registered it, it'll just be in the registry.
    
    for field_name, event_data in events.items():
        imports.add(f'import "{event_data["file"]}";')
        
        field_str = f'    {event_data["message"]} {field_name} = {event_data["index"]}'
        if event_data.get("deprecated", False):
            deprecated_fields.append(f'{field_str} [deprecated = true];')
        else:
            active_fields.append(f'{field_str};')
            
    imports_str = "\n".join(imports)
    dynamic_str = "\n".join(active_fields)
    
    if deprecated_fields:
        deprecated_str = "\n    // --- DEPRECATED EVENTS ---\n" + "\n".join(deprecated_fields)
    else:
        deprecated_str = ""
        
    main_proto_content = BASE_MAIN_PROTO_TEMPLATE.format(
        imports=imports_str,
        dynamic_fields=dynamic_str,
        deprecated_fields=deprecated_str
    )
    
    with open(MAIN_PROTO, "w") as f:
        f.write(main_proto_content)
        
    print(f"Reconstructed {MAIN_PROTO}")
    
    # Run Schema Linter / Validator
    try:
        schema_validator.validate_and_snapshot(PROTO_DIR)
    except schema_validator.SchemaValidationError as e:
        print(f"\n[!] BUILD ABORTED: {e}")
        # We must exit with a non-zero code to stop the pipeline
        import sys
        sys.exit(1)
    
    # Call protoc
    cwd = os.getcwd()
    os.chdir(PROTO_DIR)
    
    files_list = glob.glob("*.proto")
    for filename in files_list:
        print(f"Compiling {filename}...")
        subprocess.run(["protoc", "--proto_path=.", "--python_out=../", filename], check=True)
        
    os.chdir(cwd)
    
    # Fix python imports
    _fix_python_imports()
    print("Build complete.")

def _fix_python_imports():
    """Applies the regex fix for absolute imports to relative imports."""
    classes_files_list = glob.glob("data_logs/*_pb2.py")
    import_string = r"import\s+\w+_pb2\sas\s\w+__\w+__pb2"
    
    for filename in classes_files_list:
        with open(filename, 'r') as file:
            lines = file.readlines()

        with open(filename, 'w') as file:
            for line in lines:
                if re.search(import_string, line):
                    file.write("from . " + line)
                else:
                    file.write(line)

def create_event(name: str, fields: list):
    """Creates a basic .proto file. fields is a list of tuples (name, type)"""
    file_name = f"{name.lower()}_event.proto"
    path = os.path.join(PROTO_DIR, file_name)
    
    if os.path.exists(path):
        raise FileExistsError(f"{path} already exists.")
        
    content = [
        'syntax = "proto3";',
        '',
        f'message {name} {{'
    ]
    
    for idx, (f_name, f_type) in enumerate(fields, start=1):
        content.append(f'    {f_type} {f_name} = {idx};')
        
    content.append('}')
    content.append('')
    
    with open(path, "w") as f:
        f.write("\n".join(content))
        
    print(f"Created {path}")

def register_event(field_name: str, message_name: str, file_name: str = None):
    """Registers the event by discovering the file name if not provided."""
    if not file_name:
        # Auto-discovery
        files = glob.glob(os.path.join(PROTO_DIR, "*.proto"))
        matches = []
        search_str = f"message {message_name} "
        search_str2 = f"message {message_name}{{"
        
        for f in files:
            with open(f, "r") as file:
                content = file.read()
                if search_str in content or search_str2 in content or f"message {message_name}\n" in content:
                    matches.append(os.path.basename(f))
                    
        if len(matches) == 0:
            raise ValueError(f"Could not find message '{message_name}' in any .proto file.")
        elif len(matches) > 1:
            raise ValueError(f"Found message '{message_name}' in multiple files: {matches}. Please use --file to specify.")
        else:
            file_name = matches[0]
            
    idx = registry.register_event(field_name, message_name, file_name)
    print(f"Registered {field_name} at index {idx}.")
    build()

def deprecate_event(field_name: str):
    registry.deprecate_event(field_name)
    print(f"Deprecated event field {field_name}.")
    build()
