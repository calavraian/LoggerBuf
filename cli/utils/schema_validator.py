import os
import json
import subprocess
from google.protobuf import descriptor_pb2

from config import ConfigManager

def get_snapshot_file():
    return os.path.join(ConfigManager().get("PROTOS_DIR", "loggerbuf_schemas"), ".loggerbuf_schema_snapshot.json")

def get_temp_desc_file():
    return os.path.join(ConfigManager().get("PROTOS_DIR", "loggerbuf_schemas"), ".temp_desc.pb")

class SchemaValidationError(Exception):
    pass

def _extract_schema_from_descriptor(desc_path: str) -> dict:
    """Reads a FileDescriptorSet and extracts a simplified schema dictionary."""
    schema = {}
    with open(desc_path, "rb") as f:
        fds = descriptor_pb2.FileDescriptorSet()
        fds.ParseFromString(f.read())
        
        for file in fds.file:
            file_dict = {}
            for msg in file.message_type:
                fields_dict = {}
                for field in msg.field:
                    fields_dict[str(field.number)] = {
                        "name": field.name,
                        "type": field.type
                    }
                file_dict[msg.name] = {"fields": fields_dict}
            schema[file.name] = file_dict
            
    return schema

def _load_snapshot() -> dict:
    snapshot_file = get_snapshot_file()
    if not os.path.exists(snapshot_file):
        return {}
    with open(snapshot_file, "r") as f:
        return json.load(f)

def _save_snapshot(schema: dict):
    snapshot_file = get_snapshot_file()
    with open(snapshot_file, "w") as f:
        json.dump(schema, f, indent=2, sort_keys=True)

def validate_and_snapshot(proto_dir: str):
    """
    Validates that current .proto files in proto_dir are backward compatible
    with the historical snapshot. If valid, updates the snapshot.
    """
    # 1. Generate descriptor set for all proto files
    proto_files = [f for f in os.listdir(proto_dir) if f.endswith('.proto')]
    if not proto_files:
        return # Nothing to validate
        
    temp_desc_file = get_temp_desc_file()
    cmd = [
        "protoc",
        f"--proto_path={proto_dir}",
        f"--descriptor_set_out={temp_desc_file}",
        "--include_imports"
    ] + [os.path.join(proto_dir, f) for f in proto_files]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise SchemaValidationError(f"Protoc compilation failed: {e.stderr}")

    # 2. Extract new schema
    try:
        new_schema = _extract_schema_from_descriptor(temp_desc_file)
    finally:
        if os.path.exists(temp_desc_file):
            os.remove(temp_desc_file)

    # 3. Load old schema
    old_schema = _load_snapshot()

    # 4. Compare
    errors = []
    
    for filename, old_file_data in old_schema.items():
        if filename not in new_schema:
            # File was deleted
            errors.append(
                f"File '{filename}' was deleted. Protobuf definitions must not be deleted. "
                f"Restore the file and mark its usage as deprecated."
            )
            continue
            
        new_file_data = new_schema[filename]
        
        for msg_name, old_msg_data in old_file_data.items():
            if msg_name not in new_file_data:
                errors.append(
                    f"Message '{msg_name}' in '{filename}' was deleted. "
                    f"Restore the message to maintain binary compatibility."
                )
                continue
                
            new_msg_data = new_file_data[msg_name]
            old_fields = old_msg_data.get("fields", {})
            new_fields = new_msg_data.get("fields", {})
            
            for tag_id, old_field_info in old_fields.items():
                if tag_id not in new_fields:
                    errors.append(
                        f"Field '{old_field_info['name']}' (Tag {tag_id}) in message '{msg_name}' ({filename}) was deleted. "
                        f"Suggestion: Restore the field and use 'loggerbuf deprecate-subfield {filename} {msg_name} {old_field_info['name']}' instead."
                    )
                    continue
                    
                new_field_info = new_fields[tag_id]
                
                if old_field_info["name"] != new_field_info["name"]:
                    errors.append(
                        f"Field Tag {tag_id} in message '{msg_name}' was renamed from '{old_field_info['name']}' to '{new_field_info['name']}'. "
                        f"Renaming breaks source compatibility. Restore the original name."
                    )
                    
                if old_field_info["type"] != new_field_info["type"]:
                    errors.append(
                        f"Field '{old_field_info['name']}' (Tag {tag_id}) in message '{msg_name}' changed its internal data type. "
                        f"This corrupts historical binary data. Revert the type change and create a new field if a new type is needed."
                    )

    if errors:
        error_msg = "\n".join([f" - {err}" for err in errors])
        raise SchemaValidationError(
            "SCHEMA VALIDATION FAILED. Destructive changes detected:\n" + error_msg
        )

    # 5. If successful, save new snapshot
    _save_snapshot(new_schema)
