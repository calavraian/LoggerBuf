import pytest
import os
from unittest.mock import patch
from loggerbuf.cli.handlers import protos
from loggerbuf.cli.utils import registry

from click.testing import CliRunner
from loggerbuf.cli.console import cli

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
    original_cwd = os.getcwd()
    
    try:
        os.chdir(tmp_path)
        runner = CliRunner()
        # 0. Setup base protos
        # (Removed, init does this automatically)
        
        # 1. Init
        result = runner.invoke(cli, ["init"])
        if result.exit_code != 0:
            print("INIT FAILED:")
            print(result.output)
            print(result.exception)
            
        assert os.path.exists("loggerbuf_schemas/main_data.proto")
        assert os.path.exists("loggerbuf_schemas/.loggerbuf_registry.json")
        
        # 2. Create Event
        runner.invoke(cli, ["create-event", "TestUserEvent", "--field", "test_field_1:string", "--field", "test_field_2:int32"])
        assert os.path.exists("loggerbuf_schemas/testuserevent_event.proto")
        
        # 3. Register Event
        result = runner.invoke(cli, ["register-event", "test_user_event", "TestUserEvent", "--file", "testuserevent_event.proto"])
        assert "registered and compiled successfully" in result.output
        
        # Verify Registry
        data = registry.get_registry()
        assert "test_user_event" in data["events"]
        assert data["events"]["test_user_event"]["index"] == 11
        assert data["events"]["test_user_event"]["deprecated"] is False
        
        # Verify generated files
        assert os.path.exists("loggerbuf_schemas/main_data_pb2.py")
        assert os.path.exists("loggerbuf_schemas/testuserevent_event_pb2.py")
        
        # 4. Deprecate Event
        result = runner.invoke(cli, ["deprecate-event", "test_user_event"])
        assert "deprecated successfully" in result.output
        data = registry.get_registry()
        assert data["events"]["test_user_event"]["deprecated"] is True
        
        # Check if main_data.proto has [deprecated = true]
        with open("loggerbuf_schemas/main_data.proto", "r") as f:
            content = f.read()
            assert "[deprecated = true]" in content
            
    finally:
        os.chdir(original_cwd)
