#!/usr/bin/env python3
import sys
import os
import gzip
import json
import argparse
from data_logs import main_data_pb2
from google.protobuf.json_format import MessageToDict

class LoggerBufDecoder:
    @staticmethod
    def decode_file(filepath):
        """
        Reads a length-prefixed binary log file (raw or gzipped)
        and yields deserialized main_data_pb2.Event objects.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        # Auto-detect gzipped historical log files
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

def main():
    parser = argparse.ArgumentParser(
        description="LoggerBuf CLI - Decoder & exporter for length-prefixed binary telemetry log files."
    )
    parser.add_argument(
        "input",
        help="Path to the binary telemetry file (e.g. events_MAIN.log or a gzipped backup file)."
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save the decoded records. If not specified, prints to stdout."
    )
    parser.add_argument(
        "-f", "--format",
        choices=["jsonl", "pretty"],
        default="jsonl",
        help="Output format: 'jsonl' (JSON Lines) or 'pretty' (formatted readable JSON)."
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Only display summary statistics (total counts, event types, statuses) instead of records."
    )

    args = parser.parse_args()

    try:
        event_generator = LoggerBufDecoder.decode_file(args.input)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    total_events = 0

    if args.stats:
        event_types = {}
        statuses = {}
        
        try:
            for ev in event_generator:
                total_events += 1
                # Map enum values to names
                ev_type_name = str(ev.event_type)
                status_name = str(ev.status)
                
                event_types[ev_type_name] = event_types.get(ev_type_name, 0) + 1
                statuses[status_name] = statuses.get(status_name, 0) + 1
        except Exception as e:
            print(f"Error decoding events: {e}", file=sys.stderr)

        print(f"=== LoggerBuf Telemetry Statistics ===")
        print(f"File: {args.input}")
        print(f"Total events decoded: {total_events}")
        
        print("\nEvent Types Breakdown:")
        for k, v in event_types.items():
            print(f"  - {k}: {v}")
        print("\nStatuses Breakdown:")
        for k, v in statuses.items():
            print(f"  - {k}: {v}")
        return

    # Export records
    out_f = open(args.output, "w") if args.output else sys.stdout
    try:
        for ev in event_generator:
            total_events += 1
            # Convert protobuf message to Python dict
            ev_dict = MessageToDict(ev, always_print_fields_with_no_presence=True)
            if args.format == "pretty":
                out_f.write(json.dumps(ev_dict, indent=2, ensure_ascii=False) + "\n")
            else:
                out_f.write(json.dumps(ev_dict, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error decoding events: {e}", file=sys.stderr)
    finally:
        if args.output:
            out_f.close()
            print(f"Successfully decoded {total_events} events and exported to {args.output}")

if __name__ == "__main__":
    main()
