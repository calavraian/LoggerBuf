import sys
import os
import gzip
import json
import re
from google.protobuf.json_format import MessageToDict

try:
    from data_logs import Event, CounterEvent
except ImportError:
    Event = None
    CounterEvent = None

def decode_file(filepath, verify_key=None, skip_integrity=False, is_counter=False):
    """
    Reads a length-prefixed binary log file (raw or gzipped)
    and yields deserialized Event objects.
    """
    record_class = CounterEvent if is_counter else Event
    if not record_class:
        raise ImportError(f"{record_class.__name__ if record_class else 'Event class'} is not available. Please run 'loggerbuf build' first.")
        
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    open_func = gzip.open if filepath.endswith('.gz') else open
    
    import hmac
    import hashlib
    import click

    current_hash = None
    event_index = 0

    with open_func(filepath, 'rb') as f:
        while True:
            header = f.read(4)
            if not header:
                break
            if len(header) < 4:
                click.secho(f"Warning: Truncated header found in {filepath} at position {f.tell() - len(header)}", fg='red', err=True)
                break
            
            size = int.from_bytes(header, byteorder='big')
            payload = f.read(size)
            if len(payload) < size:
                click.secho(f"Warning: Truncated payload of size {size} in {filepath}", fg='red', err=True)
                break
            
            event_index += 1
            
            try:
                event = record_class.FromString(payload)
                
                # --- HMAC Verification ---
                if not skip_integrity and verify_key:
                    if hasattr(event, "hmac_signature") and event.hmac_signature:
                        stored_sig = event.hmac_signature
                        
                        # Prepare payload for hash
                        event.ClearField("hmac_signature")
                        
                        if getattr(event, "is_chain_start", False):
                            # Start of a new chain
                            prev = event.previous_file_hash if getattr(event, "previous_file_hash", b'') else b''
                        else:
                            prev = current_hash if current_hash else b''
                            
                        clean_payload = event.SerializeToString()
                        
                        expected_hash = hmac.new(verify_key.encode('utf-8'), clean_payload + prev, hashlib.sha256).digest()
                        
                        if expected_hash != stored_sig:
                            click.secho(f"\n[!] CRITICAL ALERT: Integrity Compromised at Event #{event_index} (offset {f.tell() - size})", fg='red', err=True)
                            click.secho(f"    Calculated signature does not match stored signature.", fg='red', err=True)
                        
                        # Update running hash
                        current_hash = stored_sig
                        # Restore signature for output consistency if needed
                        event.hmac_signature = stored_sig

                yield event
            except Exception as e:
                click.secho(f"Warning: Failed to deserialize event of size {size} at index {event_index}: {e}", fg='red', err=True)

def run_decode(input_file: str, output_file: str, format: str, stats: bool, head: int, tail: int, verify_key: str = None, skip_integrity: bool = False, is_counter: bool = False):
    """Main decoding logic separated from click."""
    
    try:
        event_generator = decode_file(input_file, verify_key, skip_integrity, is_counter)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    if head:
        import itertools
        event_generator = itertools.islice(event_generator, head)
    elif tail:
        import collections
        event_generator = collections.deque(event_generator, maxlen=tail)

    total_events = 0

    if stats:
        event_types = {}
        statuses = {}
        
        try:
            for ev in event_generator:
                total_events += 1
                if is_counter:
                    ev_type_name = str(ev.counter_type)
                    status_name = "N/A"
                else:
                    ev_type_name = str(ev.event_type)
                    status_name = str(ev.status)
                
                event_types[ev_type_name] = event_types.get(ev_type_name, 0) + (ev.count if is_counter else 1)
                statuses[status_name] = statuses.get(status_name, 0) + 1
        except Exception as e:
            print(f"Error decoding events: {e}", file=sys.stderr)

        print(f"=== LoggerBuf Telemetry Statistics ===")
        print(f"File: {input_file}")
        print(f"Total events decoded: {total_events}")
        
        if is_counter:
            print("\nCounters Breakdown:")
            for k, v in event_types.items():
                print(f"  - {k}: {v} (total count)")
        else:
            print("\nEvent Types Breakdown:")
            for k, v in event_types.items():
                print(f"  - {k}: {v}")
            print("\nStatuses Breakdown:")
            for k, v in statuses.items():
                print(f"  - {k}: {v}")
        return

    out_f = open(output_file, "w") if output_file else sys.stdout
    try:
        for ev in event_generator:
            total_events += 1
            ev_dict = MessageToDict(ev, always_print_fields_with_no_presence=True)
            if format == "pretty":
                out_f.write(json.dumps(ev_dict, indent=2, ensure_ascii=False) + "\n")
            else:
                out_f.write(json.dumps(ev_dict, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error decoding events: {e}", file=sys.stderr)
    finally:
        if output_file:
            out_f.close()
            print(f"Successfully decoded {total_events} events and exported to {output_file}")


import collections
import itertools

def decode_debug_file(filepath):
    """
    Reads a jsonl log file (raw or gzipped) and yields parsed JSON objects.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    open_func = gzip.open if filepath.endswith('.gz') else open
    
    with open_func(filepath, 'rt', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to decode JSON at {filepath}:{line_num}: {e}", file=sys.stderr)

def run_decode_debug(input_file: str, grep_keyword: str = None, head: int = None, tail: int = None):
    # Warning if it is the base file without rotation ext
    basename = os.path.basename(input_file)
    if basename.endswith(".log") and not re.search(r'\d{4}-\d{2}-\d{2}', basename):
        print(f"\nWarning: You are decoding what appears to be the live active file '{basename}'. "
              f"Some final bytes might be incomplete if written concurrently.\n", file=sys.stderr)

    try:
        log_generator = decode_debug_file(input_file)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    total_logs = 0
    matched_logs = 0
    
    grep_lower = grep_keyword.lower() if grep_keyword else None

    if tail is not None and tail > 0:
        log_generator = collections.deque(log_generator, maxlen=tail)

    # Original visual format: '[{asctime}] >>{name}<< ({filename}::{caller_class}::{funcName}->{lineno}) - *{levelname}* - message::>{message}'
    try:
        for log_obj in log_generator:
            if head is not None and matched_logs >= head:
                break
                
            total_logs += 1
            
            timestamp = log_obj.get("timestamp", "Unknown")
            logger_name = log_obj.get("logger", "Unknown")
            filename = log_obj.get("file", "Unknown")
            caller_class = log_obj.get("class", "None")
            func_name = log_obj.get("function", "Unknown")
            lineno = log_obj.get("line", 0)
            level = log_obj.get("level", "UNKNOWN")
            message = log_obj.get("message", "")
            
            formatted_msg = f"[{timestamp}] >>{logger_name}<< ({filename}::{caller_class}::{func_name}->{lineno}) - *{level}* - message::>{message}"
            
            if grep_lower:
                if grep_lower not in formatted_msg.lower():
                    continue
            
            matched_logs += 1
            print(formatted_msg)
            
    except Exception as e:
        print(f"Error decoding debug logs: {e}", file=sys.stderr)
    finally:
        if grep_keyword:
            print(f"--- Filtered {matched_logs} matches out of {total_logs} total logs in {input_file} ---", file=sys.stderr)

