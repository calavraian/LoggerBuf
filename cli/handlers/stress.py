import time
import threading
import sys

def run_stress_test(num_threads: int, writes_per_thread: int):
    """
    Runs a heavy concurrent stress test for LoggerBuf.
    """
    try:
        from data_logs import main_data_pb2, event_status_pb2
        from debugger import DebuggerLog, StreamLevel, LoggerSettings
        from telemetry import TelemetryLog
    except ImportError as e:
        print(f"Error importing LoggerBuf modules: {e}")
        print("Please ensure you have run 'loggerbuf build' first.")
        sys.exit(1)

    loggerSettings = LoggerSettings(name='STRESS_TEST', stream=StreamLevel.FILE_CONSOLE)
    logger = DebuggerLog(loggerSettings)
    logger.setLoggerToDebug()

    eventLogger = TelemetryLog()

    logger.info(f"\n=== Starting Concurrency Stress Test ===")
    logger.info(f"Spawning {num_threads} threads, each writing {writes_per_thread} logs & telemetry events...")

    initial_threads = threading.active_count()
    logger.info(f"Active threads BEFORE test: {initial_threads}")

    start_time = time.time()

    def worker_task(thread_id):
        for i in range(writes_per_thread):
            logger.debug(f"Thread-{thread_id} operational log #{i}")
            
            event = main_data_pb2.Event()
            event.event_type = event_status_pb2.EventType.EVENT_GENERIC
            event.general_note = f"Concurrent stress test event {i} from Thread-{thread_id}"
            event.status = event_status_pb2.EventStatus.STATUS_ACTIVE
            eventLogger.create_event(event)

    threads = []
    for t in range(num_threads):
        thread = threading.Thread(target=worker_task, args=(t,))
        threads.append(thread)

    for thread in threads:
        thread.start()

    mid_threads = threading.active_count()
    logger.info(f"Active threads DURING concurrent stress test: {mid_threads}")

    for thread in threads:
        thread.join()

    elapsed_time = time.time() - start_time
    total_writes = num_threads * writes_per_thread

    logger.info("=== Stress Test Completed ===")
    logger.info(f"Queued {total_writes} operational logs + {total_writes} telemetry events.")
    logger.info(f"Client submission time: {elapsed_time:.4f} seconds (average {(elapsed_time / (total_writes*2)) * 1000:.4f} ms per call).")
    
    time.sleep(1.0)
    logger.info(f"Active threads AFTER test and flushing: {threading.active_count()}")
    
    metrics = eventLogger.get_metrics()
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
