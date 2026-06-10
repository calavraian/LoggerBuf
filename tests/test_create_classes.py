import pytest
import os
from unittest.mock import patch
from cli.handlers import protos
from cli.utils import registry

@pytest.mark.proto
def test_cli_protos_flow_e2e(tmp_path):
    """
    Tests the complete end-to-end flow of the new CLI:
    1. init
    2. create-event
    3. register-event
    4. build (implicit in register and init)
    5. deprecate-event
    """
    # Change current working directory to tmp_path
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # 0. Setup base protos
        import shutil
        os.makedirs("data_logs/protos", exist_ok=True)
        src_status = os.path.join(original_cwd, "data_logs/protos/event_status.proto")
        shutil.copy(src_status, "data_logs/protos/")
        
        # 1. Init
        protos.init()
        
        assert os.path.exists("data_logs/protos/main_data.proto")
        assert os.path.exists("data_logs/protos/.loggerbuf_registry.json")
        
        # 2. Create Event via parameterized input
        protos.create_event("TestSubEvent", [("val", "string"), ("num", "int32")])
        assert os.path.exists("data_logs/protos/testsubevent_event.proto")
        
        protos.register_event("test_sub_event", "TestSubEvent", "testsubevent_event.proto")
        
        # Verify Registry
        data = registry.get_registry()
        assert "test_sub_event" in data["events"]
        assert data["events"]["test_sub_event"]["index"] == 11
        assert data["events"]["test_sub_event"]["deprecated"] is False
        
        # Verify generated files
        assert os.path.exists("data_logs/main_data_pb2.py")
        assert os.path.exists("data_logs/testsubevent_event_pb2.py")
        
        # 4. Deprecate Event
        protos.deprecate_event("test_sub_event")
        data = registry.get_registry()
        assert data["events"]["test_sub_event"]["deprecated"] is True
        
        # Check if main_data.proto has [deprecated = true]
        with open("data_logs/protos/main_data.proto", "r") as f:
            content = f.read()
            assert "[deprecated = true]" in content
            
    finally:
        os.chdir(original_cwd)
