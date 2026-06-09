import datetime
import gzip
import os
import queue
import threading
import time
import settings_globals as defaults
from settings_globals import QueueStrategy

from data_logs import main_data_pb2
from queue_metrics import QueueMetrics, MetricField

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
        
        self.worker_thread = threading.Thread(target=self._process_queue, name="LoggerBuf-TelemetryWorker", daemon=True)
        self.worker_thread.start()
        
        # Cache the date of the last record at startup
        self._cached_last_date = self._get_date_last_record()


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
                # Wait for event to arrive, with a 10-minute heartbeat (600s)
                # to ensure the thread wakes up periodically and checks the stop_event
                data = self.queue.get(timeout=600.0)
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
        
        # If no file exists yet or it's empty, we just track current date
        if self._cached_last_date is None:
            self._cached_last_date = current_date
            
        last_date = self._cached_last_date
        
        should_rotate_time = current_date != last_date
        
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
            self._cached_last_date = current_date

    def _get_date_last_record(self):
        if not os.path.exists(self.current_filename) or os.path.getsize(self.current_filename) == 0:
            return None
            
        try:
            with open(self.current_filename, 'rb') as f:
                # Seek to end of file
                f.seek(0, os.SEEK_END)
                position = f.tell()
                
                # Seek back starting with 4KB, exponentially backoff up to the entire file
                seek_back = min(4096, position)
                last_event_bytes = None
                
                while not last_event_bytes:
                    f.seek(position - seek_back, os.SEEK_SET)
                    chunk = f.read(seek_back)
                    
                    # Scan length-prefixed chunks sequentially from left to right in this buffer
                    idx = 0
                    while idx <= len(chunk) - 4:
                        size = int.from_bytes(chunk[idx:idx+4], byteorder='big')
                        if idx + 4 + size <= len(chunk):
                            last_event_bytes = chunk[idx+4 : idx+4+size]
                            idx += 4 + size
                        else:
                            # Shift by 1 byte if alignment is lost
                            idx += 1
                            
                    if last_event_bytes:
                        break
                        
                    if seek_back == position:
                        # Reached the beginning of the file and still found nothing
                        break
                        
                    # Exponentially expand the read buffer backwards
                    seek_back = min(seek_back * 2, position)
                
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

class TelemetryLog:
    __instances = {}
    __lock = threading.Lock()

    def __init__(self, settings: EventSettings = None):
        if not settings:
            settings = EventSettings()
            
        with TelemetryLog.__lock:
            name = settings.get_name()
            if name not in TelemetryLog.__instances:
                self.__settings = settings
                self.__writer = BackgroundEventWriter(settings)
                TelemetryLog.__instances[name] = (self.__settings, self.__writer)
            else:
                self.__settings = TelemetryLog.__instances[name][0]
                self.__writer = TelemetryLog.__instances[name][1]

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

    def get_metrics(self, keys: list = None, output_format: str = "dict", verbose: bool = False):
        """
        Retrieves a report containing high-precision metrics on the queue's behavior.
        """
        qsize = self.__writer.queue.qsize()
        return self.__writer.metrics.get_report(current_qsize=qsize, keys=keys, output_format=output_format, verbose=verbose)


