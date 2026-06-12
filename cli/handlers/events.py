import os
import re
import click
from typing import List

PROTO_DIR = "data_logs/protos"
EVENT_STATUS_PROTO = os.path.join(PROTO_DIR, "event_status.proto")

def _read_proto() -> str:
    with open(EVENT_STATUS_PROTO, "r") as f:
        return f.read()

def _write_proto(content: str):
    with open(EVENT_STATUS_PROTO, "w") as f:
        f.write(content)

def _get_max_value(enum_content: str) -> int:
    """Finds the absolute maximum integer value used in the enum body."""
    matches = re.findall(r'=\s*(\d+)\s*;', enum_content)
    if not matches:
        return 0
    return max(int(m) for m in matches)

def _append_to_enum(proto_content: str, enum_name: str, block_name: str, items: List[str], reserve: int) -> str:
    """
    Appends a new block to an enum.
    """
    enum_pattern = re.compile(rf'(enum\s+{enum_name}\s+{{)(.*?)(^\}})', re.DOTALL | re.MULTILINE)
    match = enum_pattern.search(proto_content)
    if not match:
        raise ValueError(f"Enum {enum_name} not found in {EVENT_STATUS_PROTO}")
    
    enum_start = match.group(1)
    enum_body = match.group(2)
    enum_end = match.group(3)
    
    max_val = _get_max_value(enum_body)
    
    start_val = max_val + 1
    if start_val % 10 != 0:
        start_val = ((start_val // 10) + 1) * 10
    
    next_val = start_val
    new_block = f"\n    // Specific {enum_name} for {block_name}\n"
    
    added_lines = []
    for item in items:
        added_lines.append(f"    {item} = {next_val};")
        next_val += 1
        
    end_range = next_val + reserve - 1
    if end_range < next_val:
        end_range = next_val
        
    new_block += f"    // Range: {start_val}-{end_range}\n"
    new_block += f"    // Next value: {next_val}\n"
    if added_lines:
        new_block += "\n".join(added_lines) + "\n"
    
    new_enum_body = enum_body.rstrip() + "\n" + new_block
    new_content = proto_content[:match.start()] + enum_start + new_enum_body + enum_end + proto_content[match.end():]
    return new_content

def _add_status_to_block(proto_content: str, enum_name: str, block_keyword: str, status_name: str) -> str:
    enum_pattern = re.compile(rf'(enum\s+{enum_name}\s+{{)(.*?)(^\}})', re.DOTALL | re.MULTILINE)
    match = enum_pattern.search(proto_content)
    if not match:
        raise ValueError(f"Enum {enum_name} not found.")
    
    enum_start = match.group(1)
    enum_body = match.group(2)
    enum_end = match.group(3)
    
    block_pattern = re.compile(rf'(//.*?{block_keyword}.*?\n\s*//\s*Range:\s*\d+-\d+\n\s*//\s*Next value:\s*)(\d+)(\n(?:.*?\n)*?)', re.IGNORECASE)
    
    block_match = None
    for m in block_pattern.finditer(enum_body):
        block_match = m
        
    if not block_match:
        raise ValueError(f"Could not find reservation block for '{block_keyword}' in {enum_name}. Make sure it was created via CLI.")
    
    next_val = int(block_match.group(2))
    
    prefix = enum_body[:block_match.start(2)]
    updated_next_val = str(next_val + 1)
    suffix = enum_body[block_match.end(2):]
    
    lines = suffix.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.strip() == '' or line.strip().startswith('//'):
            insert_idx = i
            break
    else:
        insert_idx = len(lines)
        
    new_line = f"    {status_name} = {next_val};"
    lines.insert(insert_idx, new_line)
    
    new_suffix = "\n".join(lines)
    new_enum_body = prefix + updated_next_val + new_suffix
    
    new_content = proto_content[:match.start()] + enum_start + new_enum_body + enum_end + proto_content[match.end():]
    return new_content

def add_type(name: str, statuses: List[str], reserve: int):
    proto_content = _read_proto()
    
    type_name = name.upper()
    if not type_name.startswith("EVENT_"):
        type_name = f"EVENT_{type_name}"
        
    proto_content = _append_to_enum(proto_content, "EventType", name, [type_name], reserve=reserve)
    
    status_names = []
    prefix = name.upper()
    if prefix.startswith("EVENT_"):
        prefix = prefix[6:]
        
    for st in statuses:
        st_name = st.upper()
        if not st_name.startswith(f"{prefix}_STATUS_"):
            st_name = f"{prefix}_STATUS_{st_name}"
        status_names.append(st_name)
        
    proto_content = _append_to_enum(proto_content, "EventStatus", name, status_names, reserve=reserve)
    _write_proto(proto_content)
    
    click.secho(f"Event type '{name}' and its statuses added successfully to event_status.proto", fg="green")

def add_status(type_name: str, status_name: str):
    proto_content = _read_proto()
    
    prefix = type_name.upper()
    if prefix.startswith("EVENT_"):
        prefix = prefix[6:]
        
    st_name = status_name.upper()
    if not st_name.startswith(f"{prefix}_STATUS_"):
        st_name = f"{prefix}_STATUS_{st_name}"
        
    proto_content = _add_status_to_block(proto_content, "EventStatus", prefix, st_name)
    _write_proto(proto_content)
    
    click.secho(f"Status '{st_name}' added successfully to event_status.proto", fg="green")

def list_events(type_name: str = None):
    proto_content = _read_proto()
    click.secho(f"--- EventType ---", fg="cyan")
    
    enum_pattern = re.compile(r'enum\s+EventType\s+\{(.*?)\}', re.DOTALL)
    match = enum_pattern.search(proto_content)
    if match:
        for line in match.group(1).split('\n'):
            if '=' in line and not line.strip().startswith('//'):
                click.echo(line.strip())
                
    click.secho(f"\n--- EventStatus ---", fg="cyan")
    enum_pattern = re.compile(r'enum\s+EventStatus\s+\{(.*?)\}', re.DOTALL)
    match = enum_pattern.search(proto_content)
    if match:
        for line in match.group(1).split('\n'):
            if '=' in line and not line.strip().startswith('//'):
                if type_name:
                    prefix = type_name.upper()
                    if prefix.startswith("EVENT_"):
                        prefix = prefix[6:]
                    if prefix in line:
                        click.echo(line.strip())
                else:
                    click.echo(line.strip())
