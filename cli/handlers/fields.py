import os
import glob
import re
import sys
from cli.handlers.protos import PROTO_DIR, build

def _find_file_for_message(message_name: str, file_name: str = None) -> str:
    if file_name:
        path = os.path.join(PROTO_DIR, file_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File '{file_name}' not found in {PROTO_DIR}.")
        return path
        
    files = glob.glob(os.path.join(PROTO_DIR, "*.proto"))
    matches = []
    
    for f in files:
        with open(f, "r") as file:
            content = file.read()
            if f"message {message_name} " in content or f"message {message_name}{{" in content or f"message {message_name}\n" in content:
                matches.append(f)
                
    if len(matches) == 0:
        raise ValueError(f"Message '{message_name}' not found in any .proto file.")
    elif len(matches) > 1:
        basenames = [os.path.basename(m) for m in matches]
        raise ValueError(f"Found message '{message_name}' in multiple files: {basenames}. Please use --file to specify.")
        
    return matches[0]

def add_subfield(message_name: str, field_name: str, field_type: str, file_name: str = None):
    """Injects a new field into an existing proto message."""
    target_file = _find_file_for_message(message_name, file_name)
    
    with open(target_file, "r") as f:
        lines = f.readlines()
        
    in_message = False
    brace_count = 0
    max_tag = 0
    insert_idx = -1
    
    for i, line in enumerate(lines):
        if re.match(rf"^message\s+{message_name}\s*{{", line) or re.match(rf"^message\s+{message_name}\n", line):
            in_message = True
            brace_count += line.count('{') - line.count('}')
            continue
            
        if in_message:
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and '}' in line:
                insert_idx = i
                break
                
            # Only match fields at the main message level (brace_count == 1)
            if brace_count == 1:
                match = re.search(r"=\s*(\d+)\s*;", line)
                if match:
                    tag = int(match.group(1))
                    if tag > max_tag:
                        max_tag = tag
                    
    if insert_idx == -1:
        raise ValueError(f"Could not find the end of message '{message_name}'. Check syntax in {target_file}.")
        
    new_tag = max_tag + 1
    new_field = f"    {field_type} {field_name} = {new_tag};\n"
    
    lines.insert(insert_idx, new_field)
    
    with open(target_file, "w") as f:
        f.writelines(lines)
        
    print(f"Added field '{field_name}' (Tag {new_tag}) to '{message_name}' in {os.path.basename(target_file)}.")
    build()

def deprecate_subfield(message_name: str, field_name: str, file_name: str = None):
    """Marks a specific field in a sub-message as deprecated."""
    target_file = _find_file_for_message(message_name, file_name)
    
    with open(target_file, "r") as f:
        lines = f.readlines()
        
    in_message = False
    brace_count = 0
    found = False
    
    for i, line in enumerate(lines):
        if re.match(rf"^message\s+{message_name}\s*{{", line) or re.match(rf"^message\s+{message_name}\n", line):
            in_message = True
            brace_count += line.count('{') - line.count('}')
            continue
            
        if in_message:
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and '}' in line:
                break
                
            if brace_count == 1:
                if re.search(rf"\s+{field_name}\s*=", line):
                    found = True
                    if "[deprecated" in line.lower():
                        print(f"Field '{field_name}' is already deprecated.")
                        return
                    lines[i] = re.sub(r";", " [deprecated = true];", line, count=1)
                    break
                
    if not found:
        raise ValueError(f"Field '{field_name}' not found in message '{message_name}'.")
        
    with open(target_file, "w") as f:
        f.writelines(lines)
        
    print(f"Marked field '{field_name}' in '{message_name}' as deprecated in {os.path.basename(target_file)}.")
    build()
