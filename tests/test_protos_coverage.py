import pytest
import os
from unittest.mock import patch, MagicMock
from cli.handlers import protos
from cli.utils.schema_validator import SchemaValidationError

def test_build_schema_validation_error(monkeypatch):
    monkeypatch.setattr(protos.registry, "get_registry", lambda: {"events": {}})
    
    # Mock schema validator to raise error
    with patch('cli.handlers.protos.schema_validator.validate_and_snapshot') as mock_validate:
        mock_validate.side_effect = SchemaValidationError("test error")
        
        # We need to catch sys.exit
        with pytest.raises(SystemExit) as exc:
            protos.build()
        assert exc.value.code == 1

def test_create_event_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(protos, "PROTO_DIR", str(tmp_path))
    (tmp_path / "exist_event.proto").touch()
    
    with pytest.raises(FileExistsError, match="already exists"):
        protos.create_event("exist", [])

def test_register_event_discovery(tmp_path, monkeypatch):
    monkeypatch.setattr(protos, "PROTO_DIR", str(tmp_path))
    
    # create files
    f1 = tmp_path / "f1.proto"
    f2 = tmp_path / "f2.proto"
    
    f1.write_text("message MyMsg {")
    f2.write_text("message MyMsg {")
    
    # Test multiple matches
    with pytest.raises(ValueError, match="multiple files"):
        protos.register_event("field", "MyMsg", None)
        
    # Test no matches
    with pytest.raises(ValueError, match="Could not find message"):
        protos.register_event("field", "NotExist", None)

@patch('cli.handlers.protos.build')
@patch('cli.handlers.protos.registry.register_event')
def test_register_event_discovery_success(mock_reg, mock_build, tmp_path, monkeypatch):
    monkeypatch.setattr(protos, "PROTO_DIR", str(tmp_path))
    
    f1 = tmp_path / "f1.proto"
    f1.write_text("message UniqueMsg {")
    
    mock_reg.return_value = 10
    
    protos.register_event("field", "UniqueMsg", None)
    
    mock_reg.assert_called_once_with("field", "UniqueMsg", "f1.proto")
    mock_build.assert_called_once()
