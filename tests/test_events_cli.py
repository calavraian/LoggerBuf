import os
import pytest
from click.testing import CliRunner
from cli.console import cli
import data_logs.registry_pb2 as registry_pb2

def test_events_cli_add_type(tmp_path, monkeypatch):
    runner = CliRunner()
    
    # We need to mock PROTO_DIR so we don't modify the real proto file in tests.
    # Actually, the real proto file is at data_logs/protos/registry.proto
    # To test safely, we will copy the real proto to a temp dir and monkeypatch PROTO_DIR.
    import shutil
    from cli.handlers import events
    
    real_proto_dir = "data_logs/protos"
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(os.path.join(real_proto_dir, "registry.proto"), test_proto_dir / "registry.proto")
    
    monkeypatch.setattr(events, "PROTO_DIR", str(test_proto_dir))
    monkeypatch.setattr(events, "REGISTRY_PROTO", str(test_proto_dir / "registry.proto"))
    
    # Add a type without statuses
    result = runner.invoke(cli, ['event', 'add-type', 'NETWORK', '--reserve', '5'])
    assert result.exit_code == 0
    assert "[WARNING]" in result.output
    
    # Verify the proto file
    with open(test_proto_dir / "registry.proto", "r") as f:
        content = f.read()
        assert "EVENT_NETWORK =" in content
        assert "Specific EventType for NETWORK" in content
        
    # Add a type with statuses
    result = runner.invoke(cli, ['event', 'add-type', 'DATABASE', '--statuses', 'CONNECTED,DISCONNECTED', '--reserve', '3'])
    assert result.exit_code == 0
    
    with open(test_proto_dir / "registry.proto", "r") as f:
        content = f.read()
        assert "EVENT_DATABASE =" in content
        assert "DATABASE_STATUS_CONNECTED =" in content
        assert "DATABASE_STATUS_DISCONNECTED =" in content

def test_events_cli_add_status(tmp_path, monkeypatch):
    runner = CliRunner()
    
    import shutil
    from cli.handlers import events
    
    real_proto_dir = "data_logs/protos"
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(os.path.join(real_proto_dir, "registry.proto"), test_proto_dir / "registry.proto")
    
    monkeypatch.setattr(events, "PROTO_DIR", str(test_proto_dir))
    monkeypatch.setattr(events, "REGISTRY_PROTO", str(test_proto_dir / "registry.proto"))
    
    # Add status to an existing block created by add_type
    runner.invoke(cli, ['event', 'add-type', 'CACHE', '--statuses', 'HIT'])
    result = runner.invoke(cli, ['event', 'add-status', 'CACHE', 'MISS'])
    
    assert result.exit_code == 0
    
    with open(test_proto_dir / "registry.proto", "r") as f:
        content = f.read()
        assert "CACHE_STATUS_HIT =" in content
        assert "CACHE_STATUS_MISS =" in content

def test_events_cli_list(tmp_path, monkeypatch):
    runner = CliRunner()
    
    import shutil
    from cli.handlers import events
    
    real_proto_dir = "data_logs/protos"
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(os.path.join(real_proto_dir, "registry.proto"), test_proto_dir / "registry.proto")
    
    monkeypatch.setattr(events, "PROTO_DIR", str(test_proto_dir))
    monkeypatch.setattr(events, "REGISTRY_PROTO", str(test_proto_dir / "registry.proto"))
    
    result = runner.invoke(cli, ['event', 'list'])
    assert result.exit_code == 0
    assert "--- EventType ---" in result.output
    assert "--- EventStatus ---" in result.output
    assert "STATUS_UNSPECIFIED" in result.output
    
    # With filter
    result = runner.invoke(cli, ['event', 'list', 'EXAMPLE_EVENT'])
    assert result.exit_code == 0
    assert "EXAMPLE_EVENT_STATUS_STARTED" in result.output
    assert "STATUS_UNSPECIFIED" not in result.output
