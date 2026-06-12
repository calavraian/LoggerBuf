import click
import sys
import threading
from cli.handlers import protos
from cli.handlers import decode
from cli.handlers import stress
from cli.handlers import fields
from cli.handlers import events
from config import ConfigManager

@click.group()
def cli():
    """LoggerBuf CLI - Asynchronous Telemetry Framework."""
    pass

@cli.command()
def init():
    """Initializes the Protos structure and the Registry."""
    try:
        protos.init()
        click.secho("LoggerBuf initialized successfully.", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
def build():
    """Rebuilds main_data.proto and compiles all classes."""
    try:
        protos.build()
        click.secho("Build completed successfully.", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('name')
@click.option('--field', multiple=True, help="Fields in name:type format (e.g. --field age:int32)")
def create_event(name, field):
    """Creates a new .proto file for an event.
    
    If --field is not provided, an interactive wizard will start.
    """
    fields_list = []
    if field:
        for f in field:
            parts = f.split(':')
            if len(parts) != 2:
                click.secho(f"Invalid field format: {f}. Use name:type", fg="red")
                sys.exit(1)
            fields_list.append((parts[0], parts[1]))
    else:
        click.secho(f"Wizard to create event '{name}'", fg="cyan")
        while click.confirm("Add a field?"):
            f_name = click.prompt("Field name")
            f_type = click.prompt("Data type (e.g. string, int32, Enum_Name)")
            fields_list.append((f_name, f_type))
            
    try:
        protos.create_event(name, fields_list)
        click.secho(f"Event {name} created. Now register it with 'loggerbuf register-event'.", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('field_name')
@click.argument('message_name')
@click.option('--file', help="Force the filename in case of collisions.")
def register_event(field_name, message_name, file):
    """Registers an event in main_data.proto and generates the build.
    
    FIELD_NAME: Name of the variable (e.g. user_login)
    MESSAGE_NAME: Name of the proto message (e.g. UserLogin)
    """
    try:
        protos.register_event(field_name, message_name, file)
        click.secho(f"Event '{field_name}' registered and compiled successfully.", fg="green")
        click.secho(
            f"\n[TIP] Consider adding specific sub-classifications (EventTypes) and statuses (EventStatus) "
            f"for your new event using 'loggerbuf event add-type' to enable deeper telemetry analytics.",
            fg="cyan"
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('field_name')
def deprecate_event(field_name):
    """Marks an event as deprecated for safe backward compatibility."""
    try:
        protos.deprecate_event(field_name)
        click.secho(f"Event '{field_name}' marked as deprecated successfully.", fg="yellow")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('message_name')
@click.argument('field_name')
@click.argument('field_type')
@click.option('-f', '--file', help="Specify the .proto file name if the message exists in multiple files.")
def add_subfield(message_name, field_name, field_type, file):
    """Adds a new field to a specific proto message."""
    try:
        fields.add_subfield(message_name, field_name, field_type, file_name=file)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('message_name')
@click.argument('field_name')
@click.option('-f', '--file', help="Specify the .proto file name if the message exists in multiple files.")
def deprecate_subfield(message_name, field_name, file):
    """Marks a specific field in a proto message as deprecated."""
    try:
        fields.deprecate_subfield(message_name, field_name, file_name=file)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('input_file')
@click.option('-o', '--output', help="JSONL output file.")
@click.option('-f', '--format', type=click.Choice(['jsonl', 'pretty']), default='jsonl')
@click.option('--stats', is_flag=True, help="Show only statistics.")
@click.option('--head', type=int, help="First N records.")
@click.option('--tail', type=int, help="Last N records.")
def decode_logs(input_file, output, format, stats, head, tail):
    """Decodes binary telemetry files to JSON."""
    if head and tail:
        click.secho("You cannot use --head and --tail together.", fg="red")
        sys.exit(1)
    
    decode.run_decode(input_file, output, format, stats, head, tail)

@cli.command()
@click.argument('input_file')
@click.option('--grep', help="Filter logs by keyword (case-insensitive).")
@click.option('--head', type=int, help="Show only the first N logs.")
@click.option('--tail', type=int, help="Show only the last N logs.")
def decode_debug(input_file, grep, head, tail):
    """Explores historical JSON debug logs visually in the terminal."""
    decode.run_decode_debug(input_file, grep, head, tail)

@cli.group()
def event():
    """Manage Event types and statuses."""
    pass

@cli.group()
def config():
    """Manage LoggerBuf global configurations (loggerbuf.json)."""
    pass

@event.command()
@click.argument('name')
@click.option('--statuses', default="", help="Comma separated list of statuses (e.g. ST1,ST2)")
@click.option('--reserve', default=10, type=int, help="Number of extra indices to reserve for future statuses.")
def add_type(name, statuses, reserve):
    """Adds a new event type and optional statuses."""
    status_list = [s.strip() for s in statuses.split(",")] if statuses else []
    try:
        events.add_type(name, status_list, reserve)
        click.secho("\n[WARNING] You modified the .proto file.", fg="yellow")
        click.secho("Run 'loggerbuf build' to compile it, and restart your application for changes to take effect.", fg="yellow")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@event.command()
@click.argument('type_name')
@click.argument('status_name')
def add_status(type_name, status_name):
    """Adds a new status to an existing event type."""
    try:
        events.add_status(type_name, status_name)
        click.secho("\n[WARNING] You modified the .proto file.", fg="yellow")
        click.secho("Run 'loggerbuf build' to compile it, and restart your application for changes to take effect.", fg="yellow")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@event.command(name="list")
@click.argument('type_name', required=False)
def list_cmd(type_name):
    """Lists registered event types and statuses."""
    try:
        events.list_events(type_name)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Sets a configuration value in loggerbuf.json."""
    config_manager = ConfigManager()
    
    # Try casting value to int or bool if applicable
    if value.lower() in ('true', 'false'):
        parsed_value = value.lower() == 'true'
    elif value.isdigit():
        parsed_value = int(value)
    else:
        parsed_value = value
        
    config_manager.set(key, parsed_value)
    
    click.echo(f"Saved: {key} = {parsed_value}")
    
    if key == "LOG_LEVEL":
        click.secho("The ConfigWatcher will hot-reload this setting in ~5 seconds without restarting the app.", fg="green")
    else:
        click.secho(f"Warning: Modifying '{key}' requires manually restarting your application to take effect.", fg="yellow")

@config.command()
@click.argument('key')
def get(key):
    """Gets a configuration value from loggerbuf.json or default."""
    config_manager = ConfigManager()
    value = config_manager.get(key)
    if value is not None:
        click.echo(value)
    else:
        click.secho(f"Key '{key}' not found in config or defaults.", fg="red")

@cli.command()
@click.option('--threads', default=10, help="Number of concurrent threads.")
@click.option('--writes', default=200, help="Writes per thread.")
def stress_test(threads, writes):
    """Runs a performance stress test on LoggerBuf."""
    stress.run_stress_test(threads, writes)

if __name__ == '__main__':
    cli()
