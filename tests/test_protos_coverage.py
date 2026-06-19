import pytest
import os
from unittest.mock import patch, MagicMock
from loggerbuf.cli.handlers import protos
from loggerbuf.cli.utils.schema_validator import SchemaValidationError

def test_build_schema_validation_error(monkeypatch, tmp_path):
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(tmp_path))
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_main_proto", lambda: str(tmp_path / "main_data.proto"))
    monkeypatch.setattr(protos.registry, "get_registry", lambda: {"events": {}})
    
    # Mock schema validator to raise error
    with patch('loggerbuf.cli.handlers.protos.schema_validator.validate_and_snapshot') as mock_validate:
        mock_validate.side_effect = SchemaValidationError("test error")
        
        # We need to catch sys.exit
        with pytest.raises(SystemExit) as exc:
            protos.build()
        assert exc.value.code == 1

def test_create_event_file_exists(tmp_path, monkeypatch):
    """Test that creating an event that already exists fails safely."""
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(tmp_path))
    
    file_path = tmp_path / "existing_event.proto"
    file_path.write_text("dummy content")
    
    with pytest.raises(FileExistsError, match="already exists"):
        protos.create_event("existing", [("f1", "string")])

def test_register_event_discovery(tmp_path, monkeypatch):
    """Test register_event with automatic file discovery."""
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(tmp_path))
    monkeypatch.setattr("loggerbuf.cli.handlers.fields._find_file_for_message", lambda m, f=None: str(tmp_path / "mock.proto"))
    monkeypatch.setattr("loggerbuf.cli.utils.registry.register_event", lambda f, m, file: 12)
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.build", MagicMock())
    
    f1 = tmp_path / "mock.proto"
    f1.write_text("message MyMessage {")
    
    protos.register_event("my_event", "MyMessage", None)
    
@patch('loggerbuf.cli.handlers.protos.build')
@patch('loggerbuf.cli.utils.registry.register_event')
@patch('loggerbuf.cli.handlers.fields._find_file_for_message')
def test_register_event_discovery_success(mock_find, mock_reg, mock_build, tmp_path, monkeypatch):
    """Test successful auto-discovery."""
    monkeypatch.setattr("loggerbuf.cli.handlers.protos.get_protos_dir", lambda: str(tmp_path))
    
    f1 = tmp_path / "f1.proto"
    f1.write_text("message UniqueMsg {")
    
    mock_reg.return_value = 10
    
    protos.register_event("field", "UniqueMsg", None)
    
    mock_reg.assert_called_once_with("field", "UniqueMsg", "f1.proto")
    mock_build.assert_called_once()
