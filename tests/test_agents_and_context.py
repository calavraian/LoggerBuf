import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import os
from loggerbuf.cli.console import cli
from loggerbuf import schema_loader
from loggerbuf.telemetry import EventContext, TelemetryLog

registry_pb2 = schema_loader.get_registry_pb2()
EventStatus = registry_pb2.EventStatus

@patch('urllib.request.urlopen')
@patch('loggerbuf.cli.handlers.protos.init')
@patch('loggerbuf.cli.console.build')
def test_init_agents_success(mock_build, mock_protos_init, mock_urlopen, tmp_path):
    runner = CliRunner()
    
    # Mock successful download
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"# SKILL"
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    base_dir = tmp_path / ".agents" / "skills"
    base_dir.mkdir(parents=True)
    
    # Run the init command with agents flag
    result = runner.invoke(cli, ['init', '--agents', '--agents-dir', str(base_dir)])
    
    assert result.exit_code == 0
    assert "Installing Agent Skills..." in result.output
    assert "Success!" in result.output
    
    skill_file = base_dir / "loggerbuf" / "SKILL.md"
    assert skill_file.exists()
    assert skill_file.read_text() == "# SKILL"

@patch('loggerbuf.cli.handlers.protos.init')
@patch('loggerbuf.cli.console.build')
def test_init_agents_no_dir(mock_build, mock_protos_init, tmp_path):
    runner = CliRunner()
    base_dir = tmp_path / "does_not_exist"
    
    result = runner.invoke(cli, ['init', '--agents', '--agents-dir', str(base_dir)])
    
    # Even if agents download fails, init should succeed overall but print error
    assert result.exit_code == 0
    assert "does not exist" in result.output

def test_event_context_default_statuses():
    telemetry_mock = MagicMock()
    
    with EventContext(telemetry_mock, event_type=1, base_kwargs={
        "default_status": EventStatus.STATUS_COMPLETED,
        "error_status": EventStatus.STATUS_FAILED
    }) as ctx:
        ctx.attach(some_val=1)
        
    telemetry_mock.log_event.assert_called_once()
    args, kwargs = telemetry_mock.log_event.call_args
    assert kwargs['status'] == EventStatus.STATUS_COMPLETED
    assert kwargs['some_val'] == 1
    assert "default_status" not in kwargs
    assert "error_status" not in kwargs

def test_event_context_error_statuses():
    telemetry_mock = MagicMock()
    
    try:
        with EventContext(telemetry_mock, event_type=1, base_kwargs={
            "default_status": EventStatus.STATUS_COMPLETED,
            "error_status": EventStatus.STATUS_FAILED
        }) as ctx:
            raise ValueError("Test Error")
    except ValueError:
        pass
        
    telemetry_mock.log_event.assert_called_once()
    args, kwargs = telemetry_mock.log_event.call_args
    assert kwargs['status'] == EventStatus.STATUS_FAILED
