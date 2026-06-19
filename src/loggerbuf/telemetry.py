import datetime
import gzip
import os
import queue
import threading
import time
from .config import ConfigManager, QueueStrategy, ConfigKey

from . import schema_loader
main_data_pb2 = schema_loader.get_main_data_pb2()
Event = main_data_pb2.Event
CounterEvent = main_data_pb2.CounterEvent

from .queue_metrics import QueueMetrics, MetricField

class BaseSettings:
    def __init__(self, prefix: str, name: str = None, logs_base_dir: str = ".", backup_dir: str = None, file_size: int = None):
        config = ConfigManager()
        self.prefix = prefix
        self.__name = name if name is not None else config.get(f'{prefix}_LOGGER_NAME')
        self.__logs_base_dir = logs_base_dir
        self.__backup_dir = backup_dir if backup_dir is not None else config.get(f'{prefix}_BACKUP_DIR')
        self.__file_size = file_size if file_size is not None else config.get(f'{prefix}_FILE_SIZE')
        self.__base_dir = config.get(f'{prefix}_BASE_DIR')
        self.__main_file_name = config.get(f'{prefix}_MAIN_FILE_NAME')
        self.__queue_max_size = config.get(f'{prefix}_QUEUE_MAX_SIZE')
        self.__queue_strategy = config.get(f'{prefix}_QUEUE_STRATEGY')

    def get_name(self): return self.__name
    def get_logs_base_dir(self): return self.__logs_base_dir
    def get_backup_dir(self): return self.__backup_dir
    def get_file_size(self): return self.__file_size
    def get_base_dir(self): return self.__base_dir
    def get_main_file_name(self): return self.__main_file_name
    def get_queue_max_size(self): return self.__queue_max_size
    def get_queue_strategy(self): return self.__queue_strategy


class EventSettings(BaseSettings):
    def __init__(self, name: str = None, logs_base_dir: str = ".", backup_dir: str = None, file_size: int = None):
        super().__init__("EVENT", name, logs_base_dir, backup_dir, file_size)

class MetricSettings(BaseSettings):
    def __init__(self, name: str = None, logs_base_dir: str = ".", backup_dir: str = None, file_size: int = None):
        super().__init__("METRIC", name, logs_base_dir, backup_dir, file_size)


class BaseBackgroundWriter:
    def __init__(self, settings: BaseSettings, record_class):
        config = ConfigManager()
        self.settings = settings
        self.record_class = record_class
        
        self.queue = queue.Queue(maxsize=settings.get_queue_max_size())
        queue_strategy_val = settings.get_queue_strategy()
        self.strategy = QueueStrategy.LOSSLESS
        if queue_strategy_val == "LOSSY":
            self.strategy = QueueStrategy.LOSSY
        elif queue_strategy_val == "LOSSLESS":
            self.strategy = QueueStrategy.LOSSLESS
            
        self.stop_event = threading.Event()
        self.metrics = QueueMetrics()
        
        self.full_path_logs = self._get_full_path_logs()
        self.current_filename = os.path.join(self.full_path_logs, f"{settings.get_main_file_name()}_{self.settings.get_name()}.log")
        
        self.file_lock = threading.Lock()
        self._file = None
        
        self.hmac_secret_key = config.get('HMAC_SECRET_KEY')
        self._current_hash = None
        self._needs_chain_start = True
        
        # worker_thread will be started by subclass
        self.worker_thread = None
        
        self._cached_last_date = self._get_date_last_record()

    def _get_full_path_logs(self):
        logs_base_dir = self.settings.get_logs_base_dir() if self.settings.get_logs_base_dir() != "." else os.getcwd()
        full_path_logs = os.path.join(logs_base_dir, self.settings.get_base_dir())
        os.makedirs(full_path_logs, exist_ok=True)
        return full_path_logs

    def write_record(self, record):
        record.timestamp = datetime.datetime.now().isoformat()
        
        try:
            qsize = self.queue.qsize()
            if self.strategy == QueueStrategy.LOSSY:
                self.queue.put_nowait(record)
            else:
                self.queue.put(record)
            self.metrics.record_enqueue(qsize)
        except queue.Full:
            self.metrics.record_drop()

    def stop(self):
        self.stop_event.set()
        self.queue.put(None)
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join()
        if self._file and not self._file.closed:
            self._file.close()

    def _process_queue(self):
        while not self.stop_event.is_set():
            try:
                data = self.queue.get(timeout=600.0)
                if data is None:
                    self.queue.task_done()
                    break
                
                try:
                    t0 = time.perf_counter()
                    self._write_record(data)
                    duration = time.perf_counter() - t0
                    self.metrics.record_dequeue(duration, self.queue.qsize())
                except Exception as e:
                    print(f"Error in LoggerBuf telemetry worker thread: {e}")
                finally:
                    self.queue.task_done()
            except queue.Empty:
                continue

    def _write_record(self, record):
        with self.file_lock:
            self._check_rotation()
            
            if not self._file or self._file.closed:
                self._file = open(self.current_filename, 'ab')
                
            if self.hmac_secret_key:
                if self._needs_chain_start:
                    record.is_chain_start = True
                    if self._current_hash:
                        record.previous_file_hash = self._current_hash
                    self._needs_chain_start = False
                else:
                    record.is_chain_start = False
                    record.ClearField("previous_file_hash")
                
                record.ClearField("hmac_signature")
                payload = record.SerializeToString()
                
                import hmac
                import hashlib
                prev = self._current_hash if self._current_hash else b''
                new_hash = hmac.new(
                    self.hmac_secret_key.encode('utf-8'),
                    payload + prev,
                    hashlib.sha256
                ).digest()
                
                record.hmac_signature = new_hash
                self._current_hash = new_hash
            else:
                record.ClearField("hmac_signature")
                record.ClearField("previous_file_hash")
                record.is_chain_start = False

            data = record.SerializeToString()
            size = len(data)
            self._file.write(size.to_bytes(4, byteorder='big'))
            self._file.write(data)
            self._file.flush()

    def _check_rotation(self):
        current_date = datetime.datetime.now().date()
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
            self._needs_chain_start = True

    def _get_date_last_record(self):
        if not os.path.exists(self.current_filename) or os.path.getsize(self.current_filename) == 0:
            return None
            
        try:
            with open(self.current_filename, 'rb') as f:
                f.seek(0, os.SEEK_END)
                position = f.tell()
                
                seek_back = min(4096, position)
                last_event_bytes = None
                
                while not last_event_bytes:
                    f.seek(position - seek_back, os.SEEK_SET)
                    chunk = f.read(seek_back)
                    
                    idx = 0
                    while idx <= len(chunk) - 4:
                        size = int.from_bytes(chunk[idx:idx+4], byteorder='big')
                        if idx + 4 + size <= len(chunk):
                            last_event_bytes = chunk[idx+4 : idx+4+size]
                            idx += 4 + size
                        else:
                            idx += 1
                            
                    if last_event_bytes:
                        break
                        
                    if seek_back == position:
                        break
                        
                    seek_back = min(seek_back * 2, position)
                
                if last_event_bytes:
                    record = self.record_class.FromString(last_event_bytes)
                    return datetime.datetime.strptime(record.timestamp[:10], "%Y-%m-%d").date()
        except Exception as e:
            print(f"Error reading last telemetry date: {e}")
        return None

    def _do_rollover(self, current_date, last_date, reason):
        current_date_str = (last_date or current_date).strftime("%Y-%m-%d")
        backup_subdir = os.path.join(self.full_path_logs, self.settings.get_backup_dir(), current_date_str)
        os.makedirs(backup_subdir, exist_ok=True)
        base_name = f"{self.settings.get_main_file_name()}_{self.settings.get_name()}_{current_date_str}.log"
        
        max_backups = self.settings.get_max_backups()
        
        # 1. Delete the oldest backup if it exists
        oldest_backup = os.path.join(backup_subdir, f"{base_name}.{max_backups}.gz")
        if os.path.exists(oldest_backup):
            try:
                os.remove(oldest_backup)
            except Exception:
                pass
                
        # 2. Shift all existing backups up by one index
        for i in range(max_backups - 1, 0, -1):
            sfn = os.path.join(backup_subdir, f"{base_name}.{i}.gz")
            dfn = os.path.join(backup_subdir, f"{base_name}.{i + 1}.gz")
            if os.path.exists(sfn):
                try:
                    os.rename(sfn, dfn)
                except Exception:
                    pass
        
        # 3. Compress current file to index 1
        backup_filename = os.path.join(backup_subdir, f"{base_name}.1.gz")
        try:
            with open(self.current_filename, 'rb') as sf, gzip.open(backup_filename, 'wb') as df:
                df.write(sf.read())
            os.remove(self.current_filename)
        except Exception as e:
            print(f"Failed to compress and rollover telemetry file: {e}")

class EventWriter(BaseBackgroundWriter):
    def __init__(self, settings: EventSettings):
        super().__init__(settings, Event)
        self.worker_thread = threading.Thread(target=self._process_queue, name="LoggerBuf-TelemetryWorker", daemon=True)
        self.worker_thread.start()
        
    def write_event(self, event: Event):
        self.write_record(event)

class MetricWriter(BaseBackgroundWriter):
    def __init__(self, settings: MetricSettings):
        super().__init__(settings, CounterEvent)
        self.worker_thread = threading.Thread(target=self._process_queue, name="LoggerBuf-MetricWorker", daemon=True)
        self.worker_thread.start()
        
    def write_event(self, event: CounterEvent):
        self.write_record(event)

class TelemetryLog:
    __instances = {}
    __lock = threading.Lock()

    def __init__(self, settings: EventSettings = None):
        config = ConfigManager()
        if not settings:
            settings = EventSettings()
            
        with TelemetryLog.__lock:
            name = settings.get_name()
            if name not in TelemetryLog.__instances:
                self.__settings = settings
                self.__event_writer = EventWriter(settings)
                
                self.__metric_writer = None
                if config.get('METRICS_ENABLED'):
                    m_settings = MetricSettings(name=name, logs_base_dir=settings.get_logs_base_dir())
                    self.__metric_writer = MetricWriter(m_settings)
                    
                TelemetryLog.__instances[name] = (self.__settings, self.__event_writer, self.__metric_writer)
            else:
                self.__settings = TelemetryLog.__instances[name][0]
                self.__event_writer = TelemetryLog.__instances[name][1]
                self.__metric_writer = TelemetryLog.__instances[name][2]

    def create_event(self, event: Event):
        import sys
        try:
            frame = sys._getframe(1)
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
        
        import warnings
        def _check_deprecated_fields(msg, prefix=""):
            for field_descriptor, value in msg.ListFields():
                field_path = f"{prefix}{field_descriptor.name}"
                if field_descriptor.GetOptions().deprecated:
                    warnings.warn(
                        f"LoggerBuf: You are sending telemetry using a DEPRECATED field '{field_path}'."
                    )
                if field_descriptor.type == field_descriptor.TYPE_MESSAGE:
                    if field_descriptor.is_repeated:
                        for idx, item in enumerate(value):
                            _check_deprecated_fields(item, f"{field_path}[{idx}].")
                    else:
                        _check_deprecated_fields(value, f"{field_path}.")

        _check_deprecated_fields(event)
        self.__event_writer.write_event(event)

    def increment(self, counter_type, value: int = 1):
        if not self.__metric_writer:
            return
            
        event = CounterEvent()
        event.counter_type = counter_type
        event.count = value
        
        import sys
        try:
            frame = sys._getframe(1)
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
        self.__metric_writer.write_event(event)

    send = create_event

    def get_metrics(self, keys: list = None, output_format: str = "dict", verbose: bool = False):
        qsize = self.__event_writer.queue.qsize()
        return self.__event_writer.metrics.get_report(current_qsize=qsize, keys=keys, output_format=output_format, verbose=verbose)
