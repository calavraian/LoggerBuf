import json
import hashlib
import os

from config import ConfigManager

def get_registry_file():
    return os.path.join(ConfigManager().get("PROTOS_DIR", "loggerbuf_schemas"), ".loggerbuf_registry.json")

class RegistryCorruptedException(Exception):
    pass

def _calculate_hash(data: dict) -> str:
    """Calculates the deterministic SHA256 of the dictionary."""
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

def get_registry() -> dict:
    """Reads and validates the registry. If it does not exist, raises FileNotFoundError."""
    registry_file = get_registry_file()
    if not os.path.exists(registry_file):
        raise FileNotFoundError(f"Registry not found at {registry_file}. Please run 'loggerbuf init' first.")
    
    with open(registry_file, "r") as f:
        content = json.load(f)
        
    if "hash" not in content or "data" not in content:
        raise RegistryCorruptedException("Registry format is invalid.")
        
    expected_hash = _calculate_hash(content["data"])
    if content["hash"] != expected_hash:
        raise RegistryCorruptedException(
            "CRITICAL: .loggerbuf_registry.json has been manually tampered with! "
            "Hash validation failed. Please restore from backup or revert changes."
        )
    
    return content["data"]

def save_registry(data: dict):
    """Saves the registry securely by signing it with its hash."""
    registry_file = get_registry_file()
    # Ensure directory exists
    os.makedirs(os.path.dirname(registry_file), exist_ok=True)
    
    payload = {
        "hash": _calculate_hash(data),
        "data": data
    }
    with open(registry_file, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

def init_registry():
    """Creates an initial registry if it doesn't exist."""
    registry_file = get_registry_file()
    if os.path.exists(registry_file):
        return
    initial_data = {
        "next_index": 11,
        "events": {}
    }
    save_registry(initial_data)

def get_event(field_name: str) -> dict:
    """Gets a specific event from the registry."""
    data = get_registry()
    return data["events"].get(field_name)

def register_event(field_name: str, message_name: str, file_name: str) -> int:
    """Registers a new event. Returns the assigned index."""
    data = get_registry()
    
    if field_name in data["events"]:
        raise ValueError(f"Event field '{field_name}' is already registered.")
        
    index = data["next_index"]
    data["events"][field_name] = {
        "message": message_name,
        "file": file_name,
        "index": index,
        "deprecated": False
    }
    data["next_index"] += 1
    
    save_registry(data)
    return index

def deprecate_event(field_name: str):
    """Marks an event as deprecated."""
    data = get_registry()
    if field_name not in data["events"]:
        raise ValueError(f"Event field '{field_name}' not found in registry.")
        
    data["events"][field_name]["deprecated"] = True
    save_registry(data)

def is_deprecated(field_name: str) -> bool:
    """Checks if an event is deprecated without aggressively throwing a tampering exception at runtime, returning False if there's no registry."""
    try:
        data = get_registry()
        event = data["events"].get(field_name)
        if event:
            return event.get("deprecated", False)
    except Exception:
        pass
    return False
