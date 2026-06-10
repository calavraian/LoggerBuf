import sys
import os
import gzip
import json
from google.protobuf.json_format import MessageToDict

try:
    from data_logs import main_data_pb2
except ImportError:
    main_data_pb2 = None

def decode_file(filepath):
    """
    Reads a length-prefixed binary log file (raw or gzipped)
    and yields deserialized main_data_pb2.Event objects.
    """
    if not main_data_pb2:
        raise ImportError("main_data_pb2 is not available. Please run 'loggerbuf build' first.")
        
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    open_func = gzip.open if filepath.endswith('.gz') else open
    
    with open_func(filepath, 'rb') as f:
        while True:
            header = f.read(4)
            if not header:
                break
            if len(header) < 4:
                print(f"Warning: Truncated header found in {filepath} at position {f.tell() - len(header)}", file=sys.stderr)
                break
            
            size = int.from_bytes(header, byteorder='big')
            payload = f.read(size)
            if len(payload) < size:
                print(f"Warning: Truncated payload of size {size} in {filepath}", file=sys.stderr)
                break
            
            try:
                event = main_data_pb2.Event.FromString(payload)
                yield event
            except Exception as e:
                print(f"Warning: Failed to deserialize event of size {size}: {e}", file=sys.stderr)

def run_decode(input_file: str, output_file: str, format: str, stats: bool, head: int, tail: int):
    """Main decoding logic separated from click."""
    
    try:
        event_generator = decode_file(input_file)
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
                ev_type_name = str(ev.event_type)
                status_name = str(ev.status)
                
                event_types[ev_type_name] = event_types.get(ev_type_name, 0) + 1
                statuses[status_name] = statuses.get(status_name, 0) + 1
        except Exception as e:
            print(f"Error decoding events: {e}", file=sys.stderr)

        print(f"=== LoggerBuf Telemetry Statistics ===")
        print(f"File: {input_file}")
        print(f"Total events decoded: {total_events}")
        
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
