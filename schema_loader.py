import os
import sys
import importlib.util
from config import ConfigManager

def _load_module(module_name, protos_dir):
    """Dynamically loads a module from the given directory."""
    file_path = os.path.join(protos_dir, f"{module_name}.py")
    if not os.path.exists(file_path):
        return None
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        return None
        
    module = importlib.util.module_from_spec(spec)
    # Important: add to sys.modules so standard python imports in generated code work
    sys.modules[module_name] = module
    # Also keep the data_logs alias for backwards compatibility if needed
    sys.modules[f"data_logs.{module_name}"] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"Error loading {module_name} from {protos_dir}: {e}")
        return None

def get_registry_pb2():
    """Loads the dynamically generated registry_pb2 module."""
    protos_dir = ConfigManager().get("PROTOS_DIR", "loggerbuf_schemas")
    mod = _load_module("registry_pb2", protos_dir)
    if mod is None:
        # Fallback to default internal for testing or pre-init
        from data_logs import registry_pb2 as internal_mod
        return internal_mod
    return mod

def get_main_data_pb2():
    """Loads the dynamically generated main_data_pb2 module."""
    protos_dir = ConfigManager().get("PROTOS_DIR", "loggerbuf_schemas")
    mod = _load_module("main_data_pb2", protos_dir)
    if mod is None:
        # Fallback to default internal
        from data_logs import main_data_pb2 as internal_mod
        return internal_mod
    return mod

def get_module(module_name):
    """Loads an arbitrary _pb2 module."""
    protos_dir = ConfigManager().get("PROTOS_DIR", "loggerbuf_schemas")
    mod = _load_module(module_name, protos_dir)
    if mod is None:
        try:
            # Fallback
            return __import__(f"data_logs.{module_name}", fromlist=[None])
        except ImportError:
            return None
    return mod
