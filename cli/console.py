import click
import sys
from cli.handlers import protos
from cli.handlers import decode
from cli.handlers import stress
from cli.handlers import fields

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
@click.option('--threads', default=10, help="Number of concurrent threads.")
@click.option('--writes', default=200, help="Writes per thread.")
def stress_test(threads, writes):
    """Runs a performance stress test on LoggerBuf."""
    stress.run_stress_test(threads, writes)

if __name__ == '__main__':
    cli()
