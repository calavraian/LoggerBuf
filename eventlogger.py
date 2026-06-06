import datetime
import gzip
import os
import queue
import threading
import time
import settings_globals as defaults

from data_logs import main_data_pb2

class QueueMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.peak_size = 0
        self.total_queued = 0
        self.total_processed = 0
        self.total_drops = 0
        self.empty_count = 0
        self.total_write_time = 0.0
        self.min_write_time = float('inf')
        self.max_write_time = 0.0
        self.drain_start_time = None
        self.total_drain_time = 0.0

    def record_enqueue(self, current_qsize):
        with self.lock:
            self.total_queued += 1
            actual_size = current_qsize + 1
            if actual_size > self.peak_size:
                self.peak_size = actual_size
            if actual_size == 1 and self.drain_start_time is None:
                self.drain_start_time = time.perf_counter()

    def record_dequeue(self, write_duration, current_qsize):
        with self.lock:
            self.total_processed += 1
            self.total_write_time += write_duration
            if write_duration < self.min_write_time:
                self.min_write_time = write_duration
            if write_duration > self.max_write_time:
                self.max_write_time = write_duration
                
            if current_qsize == 0:
                self.empty_count += 1
                if self.drain_start_time is not None:
                    duration = time.perf_counter() - self.drain_start_time
                    self.total_drain_time += duration
                    self.drain_start_time = None

    def record_drop(self):
        with self.lock:
            self.total_drops += 1

    def get_report(self):
        with self.lock:
            avg_write = (self.total_write_time / self.total_processed * 1000) if self.total_processed > 0 else 0.0
            min_write = (self.min_write_time * 1000) if self.min_write_time != float('inf') else 0.0
            max_write = (self.max_write_time * 1000)
            
            return {
                "total_queued": self.total_queued,
                "total_processed": self.total_processed,
                "total_drops": self.total_drops,
                "peak_size": self.peak_size,
                "empty_count": self.empty_count,
                "avg_write_time_ms": avg_write,
                "min_write_time_ms": min_write,
                "max_write_time_ms": max_write,
                "total_drain_time_s": self.total_drain_time
            }


class EventSettings:
    def __init__(
            self,
            logs_base_dir: str = ".",
            backup_dir: str = defaults.EVENT_BACKUP_DIR,
            file_size = defaults.EVENT_FILE_SIZE,
        ):
        """
        Constructor for EventSettings.

        Parameters
        ----------
        logs_base_dir : str, optional
            Base directory for events. Defaults to "." (current dir).
        backup_dir : str, optional
            Directory for backup event files. Defaults to "history".
        file_size : int, optional
            Maximum size of each event file in bytes.
        """
        self.__name = defaults.EVENT_LOGGER_NAME
        self.__logs_base_dir = logs_base_dir
        self.__backup_dir = backup_dir
        self.__file_size = file_size
    
    def get_name(self):
        """
        Gets the name of the logger.

        Returns
        -------
        str
            The name of the logger.
        """
        return self.__name
    
    def get_logs_base_dir(self):        
        """
        Gets the base directory for event file.

        Returns
        -------
        str
            The base directory for event file.
        """
        return self.__logs_base_dir
    
    def get_backup_dir(self):
        """
        Gets the directory for backup event files.

        Returns
        -------
        str
            The directory for backup event files.
        """
        return self.__backup_dir
    
    def get_file_size(self):
        """
        Gets the maximum size of each event file.

        Returns
        -------
        int
            The maximum size of each event file in bytes.
        """
        return self.__file_size

class BackgroundEventWriter:
    def __init__(self, settings: EventSettings):
        self.settings = settings
        from settings_globals import QueueStrategy
        self.queue = queue.Queue(maxsize=getattr(defaults, 'EVENT_QUEUE_MAX_SIZE', 10000))
        self.strategy = getattr(defaults, 'EVENT_QUEUE_STRATEGY', QueueStrategy.LOSSLESS)
        self.stop_event = threading.Event()
        
        # In-memory Metrics Collector
        self.metrics = QueueMetrics()
        
        # Track active file
        self.full_path_logs = self._get_full_path_logs()
        self.current_filename = os.path.join(self.full_path_logs, f"{defaults.EVENT_MAIN_FILE_NAME}_{self.settings.get_name()}.log")
        
        self.file_lock = threading.Lock()
        self._file = None
        
        # Start Worker Thread
        self.worker_thread = threading.Thread(target=self._process_queue, name="LoggerBuf-TelemetryWorker", daemon=True)
        self.worker_thread.start()


    def _get_full_path_logs(self):
        logs_base_dir = self.settings.get_logs_base_dir() if self.settings.get_logs_base_dir() != "." else os.getcwd()
        full_path_logs = os.path.join(logs_base_dir, defaults.EVENT_BASE_DIR)
        os.makedirs(full_path_logs, exist_ok=True)
        return full_path_logs

    def write_event(self, event: main_data_pb2.Event):
        # Stamp timestamp on caller thread to represent when event actually happened
        event.timestamp = datetime.datetime.now().isoformat()
        
        # Serialize to binary bytes on caller thread (fast & safe)
        serialized_data = event.SerializeToString()
        
        try:
            qsize = self.queue.qsize()
            if self.strategy == QueueStrategy.LOSSY:
                self.queue.put_nowait(serialized_data)
            else:
                self.queue.put(serialized_data)
            self.metrics.record_enqueue(qsize)
        except queue.Full:
            self.metrics.record_drop()

    def stop(self):
        self.stop_event.set()
        self.queue.put(None)
        if self.worker_thread.is_alive():
            self.worker_thread.join()
        if self._file and not self._file.closed:
            self._file.close()

    def _process_queue(self):
        while not self.stop_event.is_set():
            try:
                # Wait for event to arrive
                data = self.queue.get(timeout=1.0)
                if data is None:
                    self.queue.task_done()
                    break
                
                t0 = time.perf_counter()
                self._write_record(data)
                duration = time.perf_counter() - t0
                
                self.metrics.record_dequeue(duration, self.queue.qsize())
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in LoggerBuf telemetry worker thread: {e}")


    def _write_record(self, data: bytes):
        with self.file_lock:
            # Check size and date rotation before writing
            self._check_rotation()
            
            if not self._file or self._file.closed:
                self._file = open(self.current_filename, 'ab')
                
            # Write Length-Prefixed Frame
            # 4-byte big-endian integer representing message size, then the protobuf payload
            size = len(data)
            self._file.write(size.to_bytes(4, byteorder='big'))
            self._file.write(data)
            self._file.flush()

    def _check_rotation(self):
        current_date = datetime.datetime.now().date()
        last_date = self._get_date_last_record()
        
        should_rotate_time = last_date is not None and current_date != last_date
        
        should_rotate_size = False
        if os.path.exists(self.current_filename):
            size = os.path.getsize(self.current_filename)
            if size >= self.settings.get_file_size():
                should_rotate_size = True
                
        if should_rotate_time or should_rotate_size:
            if self._file and not self._file.closed:
                self._file.close()
                self._file = None
            
            self._do_rollover(current_date, last_date, "TIME" if should_rotate_time else "SIZE")

    def _get_date_last_record(self):
        if not os.path.exists(self.current_filename) or os.path.getsize(self.current_filename) == 0:
            return None
            
        try:
            with open(self.current_filename, 'rb') as f:
                # Seek to end of file
                f.seek(0, os.SEEK_END)
                position = f.tell()
                
                # Seek back up to 4KB to read the last complete record
                seek_back = min(4096, position)
                f.seek(position - seek_back, os.SEEK_SET)
                chunk = f.read(seek_back)
                
                # Scan length-prefixed chunks sequentially from left to right in this buffer
                idx = 0
                last_event_bytes = None
                while idx <= len(chunk) - 4:
                    size = int.from_bytes(chunk[idx:idx+4], byteorder='big')
                    if idx + 4 + size <= len(chunk):
                        last_event_bytes = chunk[idx+4 : idx+4+size]
                        idx += 4 + size
                    else:
                        # Shift by 1 byte if alignment is lost, or break if end is reached
                        idx += 1
                
                if last_event_bytes:
                    event = main_data_pb2.Event.FromString(last_event_bytes)
                    return datetime.datetime.strptime(event.timestamp[:10], "%Y-%m-%d").date()
        except Exception as e:
            print(f"Error reading last telemetry date: {e}")
        return None

    def _do_rollover(self, current_date, last_date, reason):
        current_date_str = (last_date or current_date).strftime("%Y-%m-%d")
        backup_subdir = os.path.join(self.full_path_logs, self.settings.get_backup_dir(), current_date_str)
        os.makedirs(backup_subdir, exist_ok=True)
        
        base_name = f"{defaults.EVENT_MAIN_FILE_NAME}_{self.settings.get_name()}"
        
        index = 1
        while True:
            backup_filename = os.path.join(backup_subdir, f"{base_name}_{current_date_str}.log.{index}.gz")
            if not os.path.exists(backup_filename):
                break
            index += 1
            if index > 1000:
                break
        
        try:
            with open(self.current_filename, 'rb') as sf, gzip.open(backup_filename, 'wb') as df:
                df.write(sf.read())
            os.remove(self.current_filename)
        except Exception as e:
            print(f"Failed to compress and rollover telemetry file: {e}")

class EventLogger:
    __instances = {}
    __lock = threading.Lock()

    def __init__(self, settings: EventSettings = None):
        if not settings:
            settings = EventSettings()
            
        with EventLogger.__lock:
            name = settings.get_name()
            if name not in EventLogger.__instances:
                self.__settings = settings
                self.__writer = BackgroundEventWriter(settings)
                EventLogger.__instances[name] = (self.__settings, self.__writer)
            else:
                self.__settings = EventLogger.__instances[name][0]
                self.__writer = EventLogger.__instances[name][1]

    def create_event(self, event: main_data_pb2.Event):
        # Extract caller information
        import sys
        try:
            # Stack level 2 gets the caller of create_event or send
            frame = sys._getframe(2)
            
            # Check if called via alias 'send', adjust frame level if so
            if frame.f_code.co_name == 'send':
                frame = sys._getframe(3)

            event.caller_file = os.path.basename(frame.f_code.co_filename)
            event.caller_function = frame.f_code.co_name
            event.lineno = frame.f_lineno
            
            if 'self' in frame.f_locals:
                event.caller_class = frame.f_locals['self'].__class__.__name__
            else:
                event.caller_class = "None"
                
        except Exception:
            event.caller_file = "Unknown"
            event.caller_function = "Unknown"
            event.lineno = 0
            event.caller_class = "Unknown"
            
        event.logger_name = self.__settings.get_name()
        
        self.__writer.write_event(event)

    # Alias to offer a cleaner telemetry API
    send = create_event

    def get_metrics(self):
        """
        Retrieves a report containing high-precision metrics on the queue's behavior.
        """
        return self.__writer.metrics.get_report()


