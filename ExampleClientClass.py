import time
import threading
from data_logs import main_data_pb2, event_status_pb2, event_example_pb2
from debulogger import Logger, StreamLevel, LoggerSettings
from eventlogger import EventLogger
from decoder import LoggerBufDecoder

class ExampleClientClass:
    def __init__(self):
        # Configure debug logger to output to both console and file
        loggerSettings = LoggerSettings(name='MAIN_LOGIC', stream=StreamLevel.FILE_CONSOLE)
        self.logger = Logger(loggerSettings)
        self.logger.setLoggerToDebug()

        # Initialize Event Logger (Telemetry)
        self.eventLogger = EventLogger()

    def run_basic_demo(self):
        """Demonstrates simple API usage."""
        self.logger.info("=== Starting LoggerBuf Basic Demo ===")
        self.logger.debug("Esto es un log de depuración (DEBUG)")
        self.logger.info("Esto es un log informativo operativo (INFO)")

        # Create structured telemetry event
        example_event = event_example_pb2.ExampleSubEvent()
        example_event.name = "Operación de Lectura"
        example_event.description = "Lectura de perfil de usuario en base de datos"
        example_event.counter = 42
        example_event.operation_type = event_example_pb2.ExampleSubEvent.OperationType.OPERATION_DATA_READ

        main_data = main_data_pb2.Event()
        main_data.event_type = event_status_pb2.EventTypes.EXAMPLE_EVENT_API_INVOKED
        main_data.general_note = "Llamada API desde módulo principal"
        main_data.status = event_status_pb2.Status.EXAMPLE_EVENT_STATUS_STARTED
        main_data.example_sub_event.CopyFrom(example_event)

        # Telemetry is put in the bounded memory queue instantly
        self.eventLogger.create_event(main_data)
        self.logger.info("Basic demo events queued successfully!")

    def run_stress_test(self, num_threads=10, writes_per_thread=200):
        """
        Runs a heavy concurrent stress test.
        Spawns multiple threads writing logs and telemetry events simultaneously.
        Measures thread count and processing times.
        """
        self.logger.info(f"\n=== Starting Concurrency Stress Test ===")
        self.logger.info(f"Spawning {num_threads} threads, each writing {writes_per_thread} logs & telemetry events...")

        initial_threads = threading.active_count()
        self.logger.info(f"Active threads BEFORE test: {initial_threads}")

        start_time = time.time()

        def worker_task(thread_id):
            for i in range(writes_per_thread):
                # Write operational debug log
                self.logger.debug(f"Thread-{thread_id} operational log #{i}")
                
                # Write telemetry event
                event = main_data_pb2.Event()
                event.event_type = event_status_pb2.EventTypes.EVENT_GENERIC
                event.general_note = f"Concurrent stress test event {i} from Thread-{thread_id}"
                event.status = event_status_pb2.Status.STATUS_ACTIVE
                self.eventLogger.create_event(event)

        # Spawn threads
        threads = []
        for t in range(num_threads):
            thread = threading.Thread(target=worker_task, args=(t,))
            threads.append(thread)

        for thread in threads:
            thread.start()

        # Capture thread count while test is running
        mid_threads = threading.active_count()
        self.logger.info(f"Active threads DURING concurrent stress test: {mid_threads}")

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        elapsed_time = time.time() - start_time
        total_writes = num_threads * writes_per_thread

        self.logger.info("=== Stress Test Completed ===")
        self.logger.info(f"Queued {total_writes} operational logs + {total_writes} telemetry events.")
        self.logger.info(f"Client submission time: {elapsed_time:.4f} seconds (average {(elapsed_time / (total_writes*2)) * 1000:.4f} ms per call).")
        
        # Give background worker threads a brief moment to finish flushing to disk
        time.sleep(1.0)
        self.logger.info(f"Active threads AFTER test and flushing: {threading.active_count()}")
        
        # Retrieve and display high-precision queue metrics
        metrics = self.eventLogger.get_metrics()
        print("\n" + "="*60)
        print("📊 LOGGERBUF TELEMETRY QUEUE METRICS DASHBOARD 📊")
        print("="*60)
        print(f" - Total Events Queued:                        {metrics['total_queued']}")
        print(f" - Total Events Processed (Written to disk):    {metrics['total_processed']}")
        print(f" - Total Events Dropped (Queue Overflow):       {metrics['total_drops']}")
        print(f" - Peak Concurrent Queue Size (Max Depth):     {metrics['peak_size']}")
        print(f" - Queue-Empty Transitions (Fully Caught Up):  {metrics['empty_count']}")
        print(f" - Average Disk Write Time:                    {metrics['avg_write_time_ms']:.4f} ms")
        print(f" - Min Disk Write Time:                        {metrics['min_write_time_ms']:.4f} ms")
        print(f" - Max Disk Write Time:                        {metrics['max_write_time_ms']:.4f} ms")
        print(f" - Total Queue Ingestion Duration (Draining):  {metrics['total_drain_time_s']:.4f} seconds")
        if metrics['total_drain_time_s'] > 0:
            speed = metrics['total_processed'] / metrics['total_drain_time_s']
            print(f" - Ingestion Inflow Processing Speed:          {speed:.1f} events/second")
        print("="*60 + "\n")


if __name__ == "__main__":
    demo = ExampleClientClass()
    
    # 1. Run basic API demo
    demo.run_basic_demo()
    
    # 2. Run high-performance concurrency stress test
    # This will write 2,000 logs and 2,000 events (4,000 total) concurrently
    demo.run_stress_test(num_threads=10, writes_per_thread=200)

    # 3. Use our new decoder to verify structural binary output integrity
    time.sleep(0.5) # ensure flushed
    event_log_file = "events/events_MAIN.log"
    print(f"\n=== Running LoggerBufDecoder on resulting file '{event_log_file}' ===")
    
    try:
        decoded_events = list(LoggerBufDecoder.decode_file(event_log_file))
        print(f"Successfully decoded {len(decoded_events)} structured events from binary format!")
        
        # Print a sample of the decoded records
        if decoded_events:
            print("\nSample Decoded Event (Protobuf to Python Dict):")
            from google.protobuf.json_format import MessageToDict
            print(MessageToDict(decoded_events[-1], always_print_fields_with_no_presence=True))
    except Exception as e:
        print(f"Failed to decode telemetry file: {e}")
