import os
import re
import subprocess
import glob
from cli.utils import registry
from cli.utils import schema_validator

from config import ConfigManager
import shutil

def get_protos_dir():
    return ConfigManager().get("PROTOS_DIR", "loggerbuf_schemas")

def get_main_proto():
    return os.path.join(get_protos_dir(), "main_data.proto")

BASE_MAIN_PROTO_TEMPLATE = """syntax = "proto3";

import "registry.proto";
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

    // --- SECURITY & INTEGRITY ---
    // The hash of the previous rotated file, used to link files in a sequence
    bytes previous_file_hash = 9997;
    
    // Indicates if this event is the start of a new hash chain
    bool is_chain_start = 9998;
    
    // The cryptographic signature (HMAC) for this event
    bytes hmac_signature = 9999;
}}

message CounterEvent {{
    // The type of counter.
    enum_control.CounterType counter_type = 1;

    // The timestamp of the event
    string timestamp = 2;

    // The count value
    int32 count = 3;

    // The name of the Logger instance
    string logger_name = 4;

    // Caller details
    string caller_file = 5;
    string caller_class = 6;
    string caller_function = 7;
    int32 lineno = 8;
    
    // --- SECURITY & INTEGRITY ---
    // The hash of the previous rotated file, used to link files in a sequence
    bytes previous_file_hash = 9997;
    
    // Indicates if this event is the start of a new hash chain
    bool is_chain_start = 9998;
    
    // The cryptographic signature (HMAC) for this event
    bytes hmac_signature = 9999;
}}
"""

def init():
    """Initializes the proto structure and registry."""
    protos_dir = get_protos_dir()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    source_protos = os.path.join(base_dir, "data_logs", "protos")
    
    if os.path.exists(protos_dir) and os.listdir(protos_dir):
        # We don't overwrite if it already exists
        pass
    else:
        os.makedirs(protos_dir, exist_ok=True)
        # Copy base schemas
        for filename in ["registry.proto", "main_data.proto", "demo_event.proto"]:
            src = os.path.join(source_protos, filename)
            if os.path.exists(src):
                shutil.copy(src, protos_dir)
                
    registry.init_registry()

def build():
    """Builds the main_data.proto based on registry and calls protoc."""
    protos_dir = get_protos_dir()
    main_proto = get_main_proto()
    
    data = registry.get_registry()
    events = data.get("events", {})
    
    imports = set()
    active_fields = []
    deprecated_fields = []
    
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
    
    with open(main_proto, "w") as f:
        f.write(main_proto_content)
        
    print(f"Reconstructed {main_proto}")
    
    # Run Schema Linter / Validator
    try:
        schema_validator.validate_and_snapshot(protos_dir)
    except schema_validator.SchemaValidationError as e:
        print(f"\n[!] BUILD ABORTED: {e}")
        # We must exit with a non-zero code to stop the pipeline
        import sys
        sys.exit(1)
    
    # Call protoc
    cwd = os.getcwd()
    os.chdir(protos_dir)
    
    files_list = glob.glob("*.proto")
    for filename in files_list:
        print(f"Compiling {filename}...")
        subprocess.run(["protoc", "--proto_path=.", "--python_out=.", filename], check=True)
        
    os.chdir(cwd)
    
    # Fix python imports and inject WARNING header
    _fix_python_imports(protos_dir)
    
    # Generate __init__.py for IDE autocomplete
    _generate_init_facade(protos_dir)
    
    print("Build complete.")

def _generate_init_facade(protos_dir):
    """Generates an __init__.py file that imports all generated classes for IDE autocompletion."""
    init_path = os.path.join(protos_dir, "__init__.py")
    classes_files_list = glob.glob(os.path.join(protos_dir, "*_pb2.py"))
    
    with open(init_path, "w") as f:
        f.write("# WARNING: DO NOT EDIT THIS FILE MANUALLY.\n")
        f.write("# This file was automatically generated by LoggerBuf for IDE autocompletion.\n\n")
        # Ensure imports are sorted for consistency
        for filepath in sorted(classes_files_list):
            module_name = os.path.basename(filepath).replace(".py", "")
            f.write(f"from .{module_name} import *\n")

def _fix_python_imports(protos_dir):
    """Applies the regex fix for absolute imports to relative imports and injects WARNING header."""
    classes_files_list = glob.glob(os.path.join(protos_dir, "*_pb2.py"))
    import_string = r"import\s+\w+_pb2"
    
    warning_header = (
        "# WARNING: DO NOT EDIT THIS FILE MANUALLY.\n"
        "# This file was automatically generated by LoggerBuf.\n"
        "# If you need to make changes, modify the corresponding .proto file\n"
        "# and run 'loggerbuf build' to regenerate this class.\n\n"
    )
    
    for filename in classes_files_list:
        with open(filename, 'r') as file:
            lines = file.readlines()

        with open(filename, 'w') as file:
            file.write(warning_header)
            for line in lines:
                if re.search(import_string, line):
                    # We remove 'from .' if they are all in the same flat folder now, 
                    # but wait, protoc in the same folder generates standard absolute imports 'import registry_pb2'
                    # which works perfectly when we inject it via schema_loader.py!
                    # Wait, no, we need to make sure the imports work correctly. Let's just leave them as they are or keep the fix if they fail.
                    # Since we add them to sys.modules via schema_loader, `import registry_pb2` works directly.
                    # Let's remove the `from .` injection.
                    file.write(line)
                else:
                    file.write(line)

def create_event(name: str, fields: list):
    """Creates a basic .proto file. fields is a list of tuples (name, type)"""
    file_name = f"{name.lower()}_event.proto"
    protos_dir = get_protos_dir()
    path = os.path.join(protos_dir, file_name)
    
    if os.path.exists(path):
        raise FileExistsError(f"File {file_name} already exists in {protos_dir}.")
        
    template = f"""syntax = "proto3";

message {name} {{
"""
    for idx, (field_name, field_type) in enumerate(fields):
        template += f"    {field_type} {field_name} = {idx + 1};\n"
        
    template += "}\n"
    
    with open(path, "w") as f:
        f.write(template)
        
    print(f"Created {path}")

def register_event(field_name: str, message_name: str, file_name: str = None):
    """Registers the event by discovering the file name if not provided."""
    protos_dir = get_protos_dir()
    if not file_name:
        # Auto-discovery
        files = glob.glob(os.path.join(protos_dir, "*.proto"))
        matches = []
        for f in files:
            with open(f, "r") as file:
                content = file.read()
                if f"message {message_name} " in content or f"message {message_name}{{" in content or f"message {message_name}\n" in content:
                    matches.append(os.path.basename(f))
                    
        if len(matches) == 0:
            raise ValueError(f"Could not find message '{message_name}' in any .proto file.")
        elif len(matches) > 1:
            raise ValueError(f"Found message '{message_name}' in multiple files: {matches}. Please specify --file.")
            
        file_name = matches[0]
        
    # verify
    if not os.path.exists(os.path.join(protos_dir, file_name)):
        raise FileNotFoundError(f"File '{file_name}' not found in {protos_dir}.")
        
    index = registry.register_event(field_name, message_name, file_name)
    print(f"Successfully registered Event: {message_name} as '{field_name}' at index {index}.")
    build()

def deprecate_event(field_name: str):
    registry.deprecate_event(field_name)
    print(f"Deprecated event field {field_name}.")
    build()
