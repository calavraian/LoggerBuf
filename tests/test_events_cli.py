import os
import pytest
from click.testing import CliRunner
from loggerbuf.cli.console import cli
import loggerbuf.data_logs.registry_pb2 as registry_pb2

def test_events_cli_add_type(tmp_path, monkeypatch):
    runner = CliRunner()
    
    # We need to mock PROTO_DIR so we don't modify the real proto file in tests.
    # Actually, the real proto file is at loggerbuf_schemas/registry.proto
    # To test safely, we will copy the real proto to a temp dir and monkeypatch get_protos_dir.
    import shutil
    import os
    from loggerbuf.cli.handlers import events
    real_proto_dir = "loggerbuf_schemas"
    if not os.path.exists(real_proto_dir):
        # Fallback to internal if not initialized
        real_proto_dir = "src/loggerbuf/data_logs/protos"
        
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(f"{real_proto_dir}/registry.proto", test_proto_dir)
    
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.fields.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.events.get_protos_dir", lambda: str(test_proto_dir))
    
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
    import os
    
    real_proto_dir = "loggerbuf_schemas"
    if not os.path.exists(real_proto_dir):
        real_proto_dir = "src/loggerbuf/data_logs/protos"
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(os.path.join(real_proto_dir, "registry.proto"), test_proto_dir / "registry.proto")
    
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.fields.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.events._get_registry_proto", lambda: str(test_proto_dir / "registry.proto"))
    
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
    import os
    
    real_proto_dir = "loggerbuf_schemas"
    if not os.path.exists(real_proto_dir):
        real_proto_dir = "src/loggerbuf/data_logs/protos"
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(os.path.join(real_proto_dir, "registry.proto"), test_proto_dir / "registry.proto")
    
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.fields.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.events._get_registry_proto", lambda: str(test_proto_dir / "registry.proto"))
    
    result = runner.invoke(cli, ['event', 'list'])
    assert result.exit_code == 0
    assert "--- EventType ---" in result.output
    assert "--- EventStatus ---" in result.output
    assert "STATUS_UNSPECIFIED" in result.output
    
    # With filter
    result = runner.invoke(cli, ['event', 'list', 'DEMO_EVENT'])
    assert result.exit_code == 0
    assert "DEMO_EVENT_STATUS_STARTED" in result.output
    assert "STATUS_UNSPECIFIED" not in result.output

def test_events_cli_add_status_overflow(tmp_path, monkeypatch):
    runner = CliRunner()
    
    import shutil
    import os
    
    real_proto_dir = "loggerbuf_schemas"
    if not os.path.exists(real_proto_dir):
        real_proto_dir = "src/loggerbuf/data_logs/protos"
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(os.path.join(real_proto_dir, "registry.proto"), test_proto_dir / "registry.proto")
    
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.fields.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.events._get_registry_proto", lambda: str(test_proto_dir / "registry.proto"))
    
    # Create a block with reserve 2 (slots: 0, 1)
    result_add = runner.invoke(cli, ['event', 'add-type', 'OVERFLOW', '--statuses', 'ONE', '--reserve', '2'])
    assert result_add.exit_code == 0, f"add-type failed: {result_add.output}"
    
    # Fill the block (slot 1)
    result_fill = runner.invoke(cli, ['event', 'add-status', 'OVERFLOW', 'TWO'])
    assert result_fill.exit_code == 0, f"add-status TWO failed: {result_fill.output}"
    
    # Attempt to exceed the block (slot 2) -> Should fail
    result_fail = runner.invoke(cli, ['event', 'add-status', 'OVERFLOW', 'THREE'])
    assert result_fail.exit_code != 0
    assert "The reserved range for block 'OVERFLOW' is full" in str(result_fail.exception) or "The reserved range for block 'OVERFLOW' is full" in result_fail.output

def test_events_cli_status_prefixing(tmp_path, monkeypatch):
    runner = CliRunner()
    
    import shutil
    import os
    
    real_proto_dir = "loggerbuf_schemas"
    if not os.path.exists(real_proto_dir):
        real_proto_dir = "src/loggerbuf/data_logs/protos"
    test_proto_dir = tmp_path / "protos"
    test_proto_dir.mkdir()
    shutil.copy(os.path.join(real_proto_dir, "registry.proto"), test_proto_dir / "registry.proto")
    
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.fields.get_protos_dir", lambda: str(test_proto_dir))
    monkeypatch.setattr("loggerbuf.cli.handlers.events._get_registry_proto", lambda: str(test_proto_dir / "registry.proto"))
    
    # 1. Add type with raw status and STATUS_ prefixed status
    runner.invoke(cli, ['event', 'add-type', 'DUMMY', '--statuses', 'RAW,STATUS_PREFIXED'])
    
    # 2. Add status with STATUS_ prefix
    runner.invoke(cli, ['event', 'add-status', 'DUMMY', 'STATUS_LATER'])
    
    with open(test_proto_dir / "registry.proto", "r") as f:
        content = f.read()
        # They should all be neatly DUMMY_STATUS_...
        assert "DUMMY_STATUS_RAW =" in content
        assert "DUMMY_STATUS_PREFIXED =" in content
        assert "DUMMY_STATUS_STATUS_PREFIXED" not in content
        assert "DUMMY_STATUS_LATER =" in content
        assert "DUMMY_STATUS_STATUS_LATER" not in content
