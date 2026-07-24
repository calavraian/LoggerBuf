import click
import sys
from ...config import ConfigManager, ConfigKey, LogMetadata

def _parse_list(val):
    if not val:
        return []
    if isinstance(val, list):
        return val
    return list(val)

def _save_list(config_mgr, key, value_list):
    config_mgr.set(key, list(value_list))

def run_status():
    config_mgr = ConfigManager()
    click.secho("\n--- LOGGERBUF FILTER STATUS ---", fg="cyan", bold=True)
    
    # Classes
    classes = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, []))
    if not classes:
        click.secho("Classes Filter: ", fg="cyan", nl=False)
        click.secho("[OFF] (All classes allowed)", fg="green")
    else:
        click.secho("Classes Filter: ", fg="cyan", nl=False)
        click.secho(f"[ACTIVE] (Only showing: {classes})", fg="yellow")
        
    # Levels
    levels = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, []))
    if not levels:
        click.secho("Levels Filter:  ", fg="cyan", nl=False)
        click.secho("[OFF] (All levels allowed)", fg="green")
    else:
        click.secho("Levels Filter:  ", fg="cyan", nl=False)
        click.secho(f"[ACTIVE] (Only showing: {levels})", fg="yellow")
        
    # Console Metadata
    default_meta = [e.value for e in LogMetadata]
    console_meta = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_METADATA, default_meta))
    missing_console = [m for m in default_meta if m not in console_meta]
    if not missing_console:
        click.secho("Console Meta:   ", fg="cyan", nl=False)
        click.secho("[OFF] (All standard fields shown)", fg="green")
    else:
        click.secho("Console Meta:   ", fg="cyan", nl=False)
        click.secho(f"[ACTIVE] (Hidden fields: {missing_console})", fg="yellow")
        
    # File Metadata
    file_meta = _parse_list(config_mgr.get(ConfigKey.LOGGING_METADATA, default_meta))
    missing_file = [m for m in default_meta if m not in file_meta]
    if not missing_file:
        click.secho("File Metadata:  ", fg="cyan", nl=False)
        click.secho("[OFF] (All standard fields saved)", fg="green")
    else:
        click.secho("File Metadata:  ", fg="cyan", nl=False)
        click.secho(f"[ACTIVE] (Hidden fields: {missing_file})", fg="yellow")
        
    click.echo("")

def run_add(cls, level, hide_metadata, hide_console_metadata):
    config_mgr = ConfigManager()
    
    if cls:
        classes = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, []))
        if cls not in classes:
            classes.append(cls)
            _save_list(config_mgr, ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, classes)
            click.secho(f"Added '{cls}' to allowed classes.", fg="green")
            
    if level:
        levels = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, []))
        level = level.upper()
        if level not in levels:
            levels.append(level)
            _save_list(config_mgr, ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, levels)
            click.secho(f"Added '{level}' to allowed levels.", fg="green")
            
    if hide_metadata:
        default_meta = [e.value for e in LogMetadata]
        current = _parse_list(config_mgr.get(ConfigKey.LOGGING_METADATA, default_meta))
        hide_metadata = hide_metadata.upper()
        if hide_metadata in current:
            current.remove(hide_metadata)
            _save_list(config_mgr, ConfigKey.LOGGING_METADATA, current)
            click.secho(f"Hidden '{hide_metadata}' from file metadata.", fg="green")
            
    if hide_console_metadata:
        default_meta = [e.value for e in LogMetadata]
        current = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_METADATA, default_meta))
        hide_console_metadata = hide_console_metadata.upper()
        if hide_console_metadata in current:
            current.remove(hide_console_metadata)
            _save_list(config_mgr, ConfigKey.LOGGING_CONSOLE_METADATA, current)
            click.secho(f"Hidden '{hide_console_metadata}' from console metadata.", fg="green")
            
    if not any([cls, level, hide_metadata, hide_console_metadata]):
        click.secho("No filters specified to add.", fg="yellow")

def run_remove(cls, level, show_metadata, show_console_metadata):
    config_mgr = ConfigManager()
    
    if cls:
        classes = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, []))
        if cls in classes:
            classes.remove(cls)
            _save_list(config_mgr, ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, classes)
            click.secho(f"Removed '{cls}' from allowed classes.", fg="green")
            
    if level:
        levels = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, []))
        level = level.upper()
        if level in levels:
            levels.remove(level)
            _save_list(config_mgr, ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, levels)
            click.secho(f"Removed '{level}' from allowed levels.", fg="green")
            
    if show_metadata:
        default_meta = [e.value for e in LogMetadata]
        current = _parse_list(config_mgr.get(ConfigKey.LOGGING_METADATA, default_meta))
        show_metadata = show_metadata.upper()
        if show_metadata not in current and show_metadata in default_meta:
            new_current = [m for m in default_meta if m in current or m == show_metadata]
            _save_list(config_mgr, ConfigKey.LOGGING_METADATA, new_current)
            click.secho(f"Restored '{show_metadata}' to file metadata.", fg="green")
            
    if show_console_metadata:
        default_meta = [e.value for e in LogMetadata]
        current = _parse_list(config_mgr.get(ConfigKey.LOGGING_CONSOLE_METADATA, default_meta))
        show_console_metadata = show_console_metadata.upper()
        if show_console_metadata not in current and show_console_metadata in default_meta:
            new_current = [m for m in default_meta if m in current or m == show_console_metadata]
            _save_list(config_mgr, ConfigKey.LOGGING_CONSOLE_METADATA, new_current)
            click.secho(f"Restored '{show_console_metadata}' to console metadata.", fg="green")
            
    if not any([cls, level, show_metadata, show_console_metadata]):
        click.secho("No filters specified to remove.", fg="yellow")

def run_reset(classes, levels, metadata, console_metadata, all):
    config_mgr = ConfigManager()
    
    if all or classes:
        config_mgr.set(ConfigKey.LOGGING_CONSOLE_ALLOWED_CLASSES, [])
        click.secho("Reset allowed classes (All allowed).", fg="green")
        
    if all or levels:
        config_mgr.set(ConfigKey.LOGGING_CONSOLE_ALLOWED_LEVELS, [])
        click.secho("Reset allowed levels (All allowed).", fg="green")
        
    if all or metadata:
        default_meta = [e.value for e in LogMetadata]
        config_mgr.set(ConfigKey.LOGGING_METADATA, default_meta)
        click.secho("Reset file metadata to defaults.", fg="green")
        
    if all or console_metadata:
        default_meta = [e.value for e in LogMetadata]
        config_mgr.set(ConfigKey.LOGGING_CONSOLE_METADATA, default_meta)
        click.secho("Reset console metadata to defaults.", fg="green")
        
    if not any([all, classes, levels, metadata, console_metadata]):
        click.secho("No reset targets specified. Use --all or specific flags.", fg="yellow")
