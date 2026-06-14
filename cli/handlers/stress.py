import time
import threading
import sys
import os
import shutil
from typing import Optional

def get_dir_size(path='.'):
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    return total

class ResourceMonitor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_event = threading.Event()
        self.peak_cpu = 0.0
        self.peak_ram_mb = 0.0
        try:
            import psutil
            self.psutil = psutil
            self.process = psutil.Process(os.getpid())
            self.enabled = True
        except ImportError:
            self.enabled = False

    def run(self):
        if not self.enabled:
            return
        while not self.stop_event.is_set():
            try:
                cpu = self.psutil.cpu_percent(interval=None)
                ram_mb = self.process.memory_info().rss / (1024 * 1024)
                if cpu > self.peak_cpu:
                    self.peak_cpu = cpu
                if ram_mb > self.peak_ram_mb:
                    self.peak_ram_mb = ram_mb
            except Exception:
                pass
            time.sleep(0.1)
            
    def stop(self):
        self.stop_event.set()

def run_stress_test(num_threads: int, total_writes: int, duration: int, queue_size: int, strategy: str, keep_logs: bool):
    """
    Runs a heavy concurrent stress test for LoggerBuf with resource monitoring.
    """
    try:
        from data_logs import main_data_pb2, event_status_pb2
        from debugger import DebuggerLog, StreamLevel, LoggerSettings
        from telemetry import TelemetryLog, EventSettings
        from config import ConfigManager
    except ImportError as e:
        print(f"Error importing LoggerBuf modules: {e}")
        print("Please ensure you have run 'loggerbuf build' first.")
        sys.exit(1)

    print("\n=== Preparing Stress Test Environment ===")
    stress_log_dir = os.path.join(os.getcwd(), 'logs', 'stress_test')
    
    # 1. Pre-cleaning
    if os.path.exists(stress_log_dir):
        print(f"Clearing old stress test directory: {stress_log_dir}")
        shutil.rmtree(stress_log_dir, ignore_errors=True)
    os.makedirs(stress_log_dir, exist_ok=True)
    
    # Measure initial disk usage (usually 0 after clean)
    initial_disk_bytes = get_dir_size(stress_log_dir)

    # 2. Config Override
    config = ConfigManager()
    with config._lock:
        original_queue_size = config._config.get('LOGGING_QUEUE_MAX_SIZE')
        original_strategy = config._config.get('LOGGING_QUEUE_STRATEGY')
        original_event_queue = config._config.get('EVENT_QUEUE_MAX_SIZE')
        original_event_strategy = config._config.get('EVENT_QUEUE_STRATEGY')
        
        config._config['LOGGING_QUEUE_MAX_SIZE'] = queue_size
        config._config['LOGGING_QUEUE_STRATEGY'] = strategy
        config._config['EVENT_QUEUE_MAX_SIZE'] = queue_size
        config._config['EVENT_QUEUE_STRATEGY'] = strategy
        
    try:
        loggerSettings = LoggerSettings(name='STRESS_TEST', stream=StreamLevel.FILE_CONSOLE)
        loggerSettings.set_path(stress_log_dir)
        logger = DebuggerLog(loggerSettings)
        logger.setLoggerToDebug()

        eventSettings = EventSettings(name='STRESS_TEST', logs_base_dir=stress_log_dir)
        eventLogger = TelemetryLog(settings=eventSettings)

        writes_per_thread = total_writes // num_threads if num_threads > 0 else 0
        delay_per_write = (duration / writes_per_thread) if writes_per_thread > 0 and duration > 0 else 0

        logger.info(f"\n=== Starting Concurrency Stress Test ===")
        logger.info(f"Target: {total_writes} total logs across {num_threads} threads ({writes_per_thread} per thread).")
        logger.info(f"Queue Size: {queue_size} | Strategy: {strategy}")
        if delay_per_write >= 0.001:
            logger.info(f"Pacing: Duration {duration}s -> ~{delay_per_write:.4f}s delay per write.")
        else:
            logger.info("Pacing: Burst mode (no artificial delay).")

        monitor = ResourceMonitor()
        monitor.start()

        start_time = time.time()

        def worker_task(thread_id):
            for i in range(writes_per_thread):
                logger.debug(f"Thread-{thread_id} operational log #{i}")
                
                event = main_data_pb2.Event()
                event.event_type = event_status_pb2.EventType.EVENT_GENERIC
                event.general_note = f"Concurrent stress test event {i} from Thread-{thread_id}"
                event.status = event_status_pb2.EventStatus.STATUS_ACTIVE
                eventLogger.create_event(event)
                
                if delay_per_write >= 0.001:
                    time.sleep(delay_per_write)

        threads = []
        for t in range(num_threads):
            thread = threading.Thread(target=worker_task, args=(t,))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        elapsed_time = time.time() - start_time
        
        # Give writer threads a moment to catch up if we are measuring drain time
        time.sleep(1.0)
        
        monitor.stop()
        monitor.join(timeout=1.0)
        
        final_disk_bytes = get_dir_size(stress_log_dir)
        disk_used_mb = (final_disk_bytes - initial_disk_bytes) / (1024 * 1024)

        logger.info("=== Stress Test Completed ===")
        logger.info(f"Client submission time: {elapsed_time:.4f} seconds.")
        
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
        print("="*60)
        print("💻 SYSTEM RESOURCES 💻")
        print("="*60)
        if monitor.enabled:
            print(f" - Peak CPU Usage:                             {monitor.peak_cpu:.1f} %")
            print(f" - Peak RAM Usage:                             {monitor.peak_ram_mb:.1f} MB")
        else:
            print(" - [psutil not installed - CPU/RAM monitoring disabled]")
        print(f" - Disk Space Consumed:                        {disk_used_mb:.2f} MB")
        print("="*60 + "\n")

    finally:
        # Restore Config
        with config._lock:
            if original_queue_size is not None:
                config._config['LOGGING_QUEUE_MAX_SIZE'] = original_queue_size
            else:
                config._config.pop('LOGGING_QUEUE_MAX_SIZE', None)
                
            if original_strategy is not None:
                config._config['LOGGING_QUEUE_STRATEGY'] = original_strategy
            else:
                config._config.pop('LOGGING_QUEUE_STRATEGY', None)
                
            if original_event_queue is not None:
                config._config['EVENT_QUEUE_MAX_SIZE'] = original_event_queue
            else:
                config._config.pop('EVENT_QUEUE_MAX_SIZE', None)
                
            if original_event_strategy is not None:
                config._config['EVENT_QUEUE_STRATEGY'] = original_event_strategy
            else:
                config._config.pop('EVENT_QUEUE_STRATEGY', None)

    # 6. Cleanup
    if not keep_logs:
        print(f"Cleaning up temporary logs in {stress_log_dir}...")
        shutil.rmtree(stress_log_dir, ignore_errors=True)
        print("Cleanup complete.")
    else:
        print(f"Logs retained in {stress_log_dir}")
