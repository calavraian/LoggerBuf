import click
import sys
from cli.handlers import protos
from cli.handlers import decode
from cli.handlers import stress

@click.group()
def cli():
    """LoggerBuf CLI - Framework de Telemetría Asíncrona."""
    pass

@cli.command()
def init():
    """Inicializa la estructura de Protos y el Registry."""
    try:
        protos.init()
        click.secho("LoggerBuf inicializado correctamente.", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
def build():
    """Reconstruye main_data.proto y compila todas las clases."""
    try:
        protos.build()
        click.secho("Build completado correctamente.", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('name')
@click.option('--field', multiple=True, help="Campos en formato nombre:tipo (ej. --field edad:int32)")
def create_event(name, field):
    """Crea un nuevo archivo .proto para un evento.
    
    Si no se pasan --field, inicia el asistente interactivo.
    """
    fields_list = []
    if field:
        for f in field:
            parts = f.split(':')
            if len(parts) != 2:
                click.secho(f"Formato de campo inválido: {f}. Use nombre:tipo", fg="red")
                sys.exit(1)
            fields_list.append((parts[0], parts[1]))
    else:
        click.secho(f"Asistente para crear evento '{name}'", fg="cyan")
        while click.confirm("¿Agregar un campo?"):
            f_name = click.prompt("Nombre del campo")
            f_type = click.prompt("Tipo de dato (ej. string, int32, Enum_Name)")
            fields_list.append((f_name, f_type))
            
    try:
        protos.create_event(name, fields_list)
        click.secho(f"Evento {name} creado. Ahora regístralo con 'loggerbuf register-event'.", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('field_name')
@click.argument('message_name')
@click.option('--file', help="Forzar el nombre del archivo si hay colisiones.")
def register_event(field_name, message_name, file):
    """Registra un evento en main_data.proto y genera el build.
    
    FIELD_NAME: Nombre de la variable (ej. user_login)
    MESSAGE_NAME: Nombre del mensaje proto (ej. UserLogin)
    """
    try:
        protos.register_event(field_name, message_name, file)
        click.secho(f"Evento '{field_name}' registrado y compilado exitosamente.", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('field_name')
def deprecate_event(field_name):
    """Marca un evento como deprecado para retrocompatibilidad segura."""
    try:
        protos.deprecate_event(field_name)
        click.secho(f"Evento '{field_name}' marcado como deprecado exitosamente.", fg="yellow")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)

@cli.command()
@click.argument('input_file')
@click.option('-o', '--output', help="Archivo de salida JSONL.")
@click.option('-f', '--format', type=click.Choice(['jsonl', 'pretty']), default='jsonl')
@click.option('--stats', is_flag=True, help="Mostrar solo estadísticas.")
@click.option('--head', type=int, help="Primeros N registros.")
@click.option('--tail', type=int, help="Últimos N registros.")
def decode_logs(input_file, output, format, stats, head, tail):
    """Decodifica archivos de telemetría binaria a JSON."""
    if head and tail:
        click.secho("No puedes usar --head y --tail juntos.", fg="red")
        sys.exit(1)
    
    decode.run_decode(input_file, output, format, stats, head, tail)

@cli.command()
@click.option('--threads', default=10, help="Número de hilos concurrentes.")
@click.option('--writes', default=200, help="Escrituras por hilo.")
def stress_test(threads, writes):
    """Ejecuta una prueba de estrés de rendimiento del LoggerBuf."""
    stress.run_stress_test(threads, writes)

if __name__ == '__main__':
    cli()
