import pytest
from unittest.mock import patch, MagicMock
from loggerbuf.cli.utils.schema_validator import validate_and_snapshot, SchemaValidationError

@patch('loggerbuf.cli.utils.schema_validator.os.listdir')
def test_validate_no_files(mock_listdir):
    mock_listdir.return_value = []
    # Should just return without error
    validate_and_snapshot("dummy_dir")

@patch('loggerbuf.cli.utils.schema_validator.os.listdir')
@patch('loggerbuf.cli.utils.schema_validator.subprocess.run')
def test_validate_protoc_error(mock_subprocess_run, mock_listdir):
    import subprocess
    mock_listdir.return_value = ['test.proto']
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, 'cmd', stderr='error')
    with pytest.raises(SchemaValidationError, match="Protoc compilation failed"):
        validate_and_snapshot("dummy_dir")

@patch('loggerbuf.cli.utils.schema_validator.os.listdir')
@patch('loggerbuf.cli.utils.schema_validator.subprocess.run')
@patch('loggerbuf.cli.utils.schema_validator._extract_schema_from_descriptor')
@patch('loggerbuf.cli.utils.schema_validator._load_snapshot')
@patch('loggerbuf.cli.utils.schema_validator.os.remove')
@patch('loggerbuf.cli.utils.schema_validator.os.path.exists')
def test_schema_validation_errors(mock_exists, mock_remove, mock_load, mock_extract, mock_run, mock_listdir):
    mock_listdir.return_value = ['test.proto']
    mock_exists.return_value = True
    
    old_schema = {
        "deleted_file.proto": {
            "MessageA": {
                "fields": {
                    "1": {"name": "fld", "type": "int32"}
                }
            }
        },
        "test.proto": {
            "DeletedMessage": {
                "fields": {}
            },
            "MessageB": {
                "fields": {
                    "1": {"name": "fld_deleted", "type": "int32"},
                    "2": {"name": "fld_renamed", "type": "int32"},
                    "3": {"name": "fld_type_changed", "type": "int32"},
                }
            }
        }
    }
    
    new_schema = {
        "test.proto": {
            "MessageB": {
                "fields": {
                    "2": {"name": "fld_newname", "type": "int32"},
                    "3": {"name": "fld_type_changed", "type": "string"},
                }
            }
        }
    }
    
    mock_load.return_value = old_schema
    mock_extract.return_value = new_schema
    
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_and_snapshot("dummy_dir")
        
    error_msg = str(exc_info.value)
    assert "SCHEMA VALIDATION FAILED" in error_msg
    assert "deleted_file.proto' was deleted" in error_msg
    assert "DeletedMessage' in 'test.proto' was deleted" in error_msg
    assert "fld_deleted' (Tag 1) in message 'MessageB' (test.proto) was deleted" in error_msg
    assert "renamed from 'fld_renamed' to 'fld_newname'" in error_msg
    assert "changed its internal data type" in error_msg
