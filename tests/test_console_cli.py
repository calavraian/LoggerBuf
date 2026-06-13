import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from cli.console import cli

@pytest.fixture
def runner():
    return CliRunner()

@patch('cli.console.protos')
def test_init(mock_protos, runner):
    result = runner.invoke(cli, ['init'])
    assert result.exit_code == 0
    assert "LoggerBuf initialized successfully" in result.output
    mock_protos.init.assert_called_once()

@patch('cli.console.protos')
def test_build(mock_protos, runner):
    result = runner.invoke(cli, ['build'])
    assert result.exit_code == 0
    assert "Build completed successfully" in result.output
    mock_protos.build.assert_called_once()

@patch('cli.console.protos')
def test_create_event_with_fields(mock_protos, runner):
    result = runner.invoke(cli, ['create-event', 'MyEvent', '--field', 'age:int32', '--field', 'name:string'])
    assert result.exit_code == 0
    assert "Event MyEvent created" in result.output
    mock_protos.create_event.assert_called_once_with('MyEvent', [('age', 'int32'), ('name', 'string')])

@patch('cli.console.protos')
def test_create_event_invalid_field(mock_protos, runner):
    result = runner.invoke(cli, ['create-event', 'MyEvent', '--field', 'age_int32'])
    assert result.exit_code == 1
    assert "Invalid field format" in result.output
    mock_protos.create_event.assert_not_called()

@patch('cli.console.protos')
def test_create_event_interactive(mock_protos, runner):
    # simulate "y" (add field?), "age", "int32", "n" (add another?)
    result = runner.invoke(cli, ['create-event', 'MyEvent'], input="y\nage\nint32\nn\n")
    assert result.exit_code == 0
    mock_protos.create_event.assert_called_once_with('MyEvent', [('age', 'int32')])

@patch('cli.console.protos')
def test_exceptions_in_commands(mock_protos, runner):
    mock_protos.init.side_effect = Exception("init error")
    result = runner.invoke(cli, ['init'])
    assert result.exit_code == 1
    assert "Error: init error" in result.output
    
    mock_protos.build.side_effect = Exception("build error")
    result = runner.invoke(cli, ['build'])
    assert result.exit_code == 1
    
    mock_protos.create_event.side_effect = Exception("create error")
    result = runner.invoke(cli, ['create-event', 'ErrEvent', '--field', 'f:string'])
    assert result.exit_code == 1
    
    mock_protos.register_event.side_effect = Exception("reg error")
    result = runner.invoke(cli, ['register-event', 'e', 'E'])
    assert result.exit_code == 1
    
    mock_protos.deprecate_event.side_effect = Exception("dep error")
    result = runner.invoke(cli, ['deprecate-event', 'e'])
    assert result.exit_code == 1

@patch('cli.console.fields')
def test_exceptions_in_fields(mock_fields, runner):
    mock_fields.add_subfield.side_effect = Exception("add error")
    result = runner.invoke(cli, ['add-subfield', 'M', 'F', 'T'])
    assert result.exit_code == 1
    
    mock_fields.deprecate_subfield.side_effect = Exception("dep error")
    result = runner.invoke(cli, ['deprecate-subfield', 'M', 'F'])
    assert result.exit_code == 1

@patch('cli.console.events')
def test_exceptions_in_events(mock_events, runner):
    mock_events.add_type.side_effect = Exception("add_type error")
    result = runner.invoke(cli, ['event', 'add-type', 'N'])
    assert result.exit_code == 1
    
    mock_events.add_status.side_effect = Exception("add_status error")
    result = runner.invoke(cli, ['event', 'add-status', 'N', 'S'])
    assert result.exit_code == 1
    
    mock_events.list_events.side_effect = Exception("list error")
    result = runner.invoke(cli, ['event', 'list'])
    assert result.exit_code == 1

@patch('cli.console.protos')
def test_register_event(mock_protos, runner):
    result = runner.invoke(cli, ['register-event', 'my_evt', 'MyEvt'])
    assert result.exit_code == 0
    assert "registered and compiled successfully" in result.output
    mock_protos.register_event.assert_called_once_with('my_evt', 'MyEvt', None)

@patch('cli.console.protos')
def test_deprecate_event(mock_protos, runner):
    result = runner.invoke(cli, ['deprecate-event', 'my_evt'])
    assert result.exit_code == 0
    assert "marked as deprecated successfully" in result.output
    mock_protos.deprecate_event.assert_called_once_with('my_evt')

@patch('cli.console.fields')
def test_add_subfield(mock_fields, runner):
    result = runner.invoke(cli, ['add-subfield', 'Msg', 'fld', 'int32'])
    assert result.exit_code == 0
    mock_fields.add_subfield.assert_called_once_with('Msg', 'fld', 'int32', file_name=None)

@patch('cli.console.fields')
def test_deprecate_subfield(mock_fields, runner):
    result = runner.invoke(cli, ['deprecate-subfield', 'Msg', 'fld'])
    assert result.exit_code == 0
    mock_fields.deprecate_subfield.assert_called_once_with('Msg', 'fld', file_name=None)

@patch('cli.console.decode')
def test_decode_logs(mock_decode, runner):
    result = runner.invoke(cli, ['decode-logs', 'file.bin'])
    assert result.exit_code == 0
    mock_decode.run_decode.assert_called_once_with('file.bin', None, 'jsonl', False, None, None)

@patch('cli.console.decode')
def test_decode_logs_head_tail_conflict(mock_decode, runner):
    result = runner.invoke(cli, ['decode-logs', 'file.bin', '--head', '10', '--tail', '10'])
    assert result.exit_code == 1
    assert "cannot use --head and --tail together" in result.output
    mock_decode.run_decode.assert_not_called()

@patch('cli.console.decode')
def test_decode_debug(mock_decode, runner):
    result = runner.invoke(cli, ['decode-debug', 'file.log'])
    assert result.exit_code == 0
    mock_decode.run_decode_debug.assert_called_once_with('file.log', None, None, None)

@patch('cli.console.stress')
def test_stress_test(mock_stress, runner):
    result = runner.invoke(cli, ['stress-test'])
    assert result.exit_code == 0
    mock_stress.run_stress_test.assert_called_once_with(10, 200)

@patch('cli.console.ConfigManager')
def test_config_set_get(mock_cm_class, runner):
    mock_cm = MagicMock()
    mock_cm_class.return_value = mock_cm
    
    mock_cm.get.return_value = "INFO"
    result = runner.invoke(cli, ['config', 'get', 'LOG_LEVEL'])
    assert result.exit_code == 0
    assert "INFO" in result.output
    mock_cm.get.assert_called_once_with('LOG_LEVEL')
    
    result = runner.invoke(cli, ['config', 'set', 'LOG_LEVEL', 'DEBUG'])
    assert result.exit_code == 0
    assert "Updated LOG_LEVEL = DEBUG" in result.output
    mock_cm.set.assert_called_once_with('LOG_LEVEL', 'DEBUG')
    
    # Test casting
    result = runner.invoke(cli, ['config', 'set', 'ENABLE', 'true'])
    assert result.exit_code == 0
    mock_cm.set.assert_called_with('ENABLE', True)
    
    result = runner.invoke(cli, ['config', 'set', 'NUM', '42'])
    assert result.exit_code == 0
    mock_cm.set.assert_called_with('NUM', 42)

@patch('cli.console.ConfigManager')
def test_config_get_not_found(mock_cm_class, runner):
    mock_cm = MagicMock()
    mock_cm_class.return_value = mock_cm
    mock_cm.get.return_value = None
    
    result = runner.invoke(cli, ['config', 'get', 'INVALID'])
    assert result.exit_code == 0
    assert "not found" in result.output

@patch('cli.console.ConfigManager')
def test_config_reset(mock_cm_class, runner):
    mock_cm = MagicMock()
    mock_cm_class.return_value = mock_cm
    mock_cm._config = {'TEST_KEY': 'some_val'}
    mock_cm.get.return_value = 'default_val'
    
    result = runner.invoke(cli, ['config', 'reset', 'TEST_KEY'])
    assert result.exit_code == 0
    assert "Reset TEST_KEY to default: default_val" in result.output
    mock_cm.remove.assert_called_once_with('TEST_KEY')
    
    result = runner.invoke(cli, ['config', 'reset', 'NOT_SET'])
    assert result.exit_code == 0
    assert "already using default" in result.output

@patch('cli.console.events')
def test_event_commands(mock_events, runner):
    result = runner.invoke(cli, ['event', 'add-type', 'NET', '--statuses', 'ON,OFF', '--reserve', '5'])
    assert result.exit_code == 0
    mock_events.add_type.assert_called_once_with('NET', ['ON', 'OFF'], 5)
    
    result = runner.invoke(cli, ['event', 'add-status', 'NET', 'IDLE'])
    assert result.exit_code == 0
    mock_events.add_status.assert_called_once_with('NET', 'IDLE')
    
    result = runner.invoke(cli, ['event', 'list', 'NET'])
    assert result.exit_code == 0
    mock_events.list_events.assert_called_once_with('NET')
