# LoggerBuf 🚀

### *Structured Telemetry & High-Performance Async Logger for Python*

`LoggerBuf` es una biblioteca de logging híbrida y de alto rendimiento diseñada para resolver un problema clásico: **la separación limpia entre logs operativos de diagnóstico (debug) y eventos de telemetría de negocio estructurados**.

A diferencia de los sistemas de logging tradicionales de texto plano, `LoggerBuf` utiliza **Protocol Buffers (Protobuf)** para garantizar esquemas de datos estables y compactos en su canal de telemetría, almacenando la información en archivos binarios optimizados con rotación automática y compresión Gzip en segundo plano, sin interferir jamás con el rendimiento de la aplicación principal.

---

## 🌟 Características Clave & Beneficios

*   **⚡ Concurrencia Desacoplada de Alta Velocidad**: Implementa el patrón *Productor-Consumidor* utilizando una cola acotada en memoria y un hilo de fondo dedicado (*Daemon Worker Thread*). Los hilos de tu aplicación principal encolan logs y retornan en microsegundos (promedio de **0.004 ms**), absorbiendo por completo la latencia de escritura en disco.
*   **🛡️ Estabilidad Garantizada (Flat Thread Pool)**: Se acabaron los hilos ad-hoc descontrolados. No importa si tu app atiende 10,000 peticiones concurrentes; `LoggerBuf` mantiene un control estricto de exactamente un solo hilo trabajador para escritura física por canal, protegiendo al sistema operativo contra el agotamiento de hilos (*Thread Exhaustion*).
*   **📦 Telemetría Binaria Compacta (Length-Prefixed)**: Los eventos de telemetría se graban en disco en formato binario puro (Length-Prefixed Framing: cabecera de 4 bytes de longitud + bytes crudos del Protobuf). Esto ocupa una fracción del espacio de un JSON tradicional y evita cualquier riesgo de corrupción por caracteres especiales o saltos de línea (`0x0A`).
*   **⚙️ Perfiles de Desborde Configurables**:
    *   `LOSSLESS` (Modo Seguro - Telemetría): Bloquea brevemente si la cola está llena, garantizando que no se pierda un solo evento de analítica.
    *   `LOSSY` (Modo Velocidad Extrema - Debug): Descarta silenciosamente los logs operativos más antiguos si la cola de disco está saturada, blindando el rendimiento de tu aplicación principal.
*   **🔍 Contexto Nativo Ultra Rápido**: Captura el archivo, la línea, la función y la clase exacta que emite cada log a nivel de C (usando el framework nativo de logging de Python), eliminando el costoso stack walking manual con `inspect` que ralentiza las aplicaciones.
*   **📊 Decodificador Asíncrono Offline (CLI)**: Incluye una potente herramienta de CLI que de forma automatizada y bajo demanda descomprime, valida, extrae métricas de rendimiento y exporta tus archivos binarios a formato JSON-Lines (JSONL) listo para ClickHouse, BigQuery o ElasticSearch.

---

## 🚀 Inicio Rápido

### 1. Inicialización e Importación Básica

El API expone dos constructores unificados de nivel superior: `get_debugger()` para logs de diagnóstico y `get_telemetry()` para eventos estructurados.

```python
import loggerbuf
from data_logs import main_data_pb2, event_status_pb2

# 1. Obtener el depurador operativo (consola + archivo asíncrono)
log = loggerbuf.get_debugger(name="MAIN_APP")
log.info("Iniciando la aplicación...")

# 2. Obtener el registrador de telemetría estructurado
telemetry = loggerbuf.get_telemetry()
```

### 2. Registro de Logs de Diagnóstico (Debugger)
El depurador soporta los niveles tradicionales de logging estándar (`debug`, `info`, `warning`, `error`, `critical`).

```python
class PaymentService:
    def process(self):
        log.info("Procesando pago de usuario...")
        try:
            # ... lógica de negocio ...
            log.debug("Conexión con pasarela establecida.")
        except Exception as e:
            log.error(f"Fallo en transacción: {e}")
```
*Salida formateada automáticamente en consola y archivo:*
`[2026-05-29 10:15:30,123] >>MAIN_APP<< (payment.py::PaymentService::process->5) - *INFO* - message::>Procesando pago de usuario...`

### 3. Registro de Eventos Analíticos (Telemetry)
Envía directamente tus mensajes estructurados de **Protobuf**.

```python
# Crear y rellenar tu mensaje Protobuf
event = main_data_pb2.Event()
event.event_type = event_status_pb2.EventTypes.EVENT_DATA_BASE_PROCESSING
event.general_note = "Usuario registrado exitosamente"
event.status = event_status_pb2.Status.STATUS_COMPLETED

# Encolado instantáneo no-bloqueante
telemetry.send(event)
```

---

## 📊 CLI Decoder (Herramienta de Ingesta Offline)

Dado que los archivos de eventos analíticos se guardan en un formato binario extremadamente compacto y rotan automáticamente en archivos `.gz` comprimidos, `LoggerBuf` incluye un decodificador de línea de comandos para procesar los datos bajo demanda.

### Obtener Estadísticas y Métricas Rápidas
```bash
python3 decoder.py events/history/2026-05-29/events_MAIN_2026-05-29.log.1.gz --stats
```
*Resultado:*
```text
=== LoggerBuf Telemetry Statistics ===
File: events/history/2026-05-29/events_MAIN_2026-05-29.log.1.gz
Total events decoded: 1540

Event Types Breakdown:
  - EVENT_DATA_BASE_PROCESSING: 1200
  - EXAMPLE_EVENT_API_INVOKED: 340

Statuses Breakdown:
  - STATUS_COMPLETED: 1200
  - EXAMPLE_EVENT_STATUS_STARTED: 340
```

### Exportar a JSON-Lines (JSONL) para bases de datos (ClickHouse, BigQuery, ELK)
```bash
python3 decoder.py events/events_MAIN.log -o raw_events.jsonl --format jsonl
```

---

## 🛠️ Configuración (`settings_globals.py`)

Puedes personalizar las características físicas del logger y los buffers en `settings_globals.py`:

```python
# Configuración del Debugger
LOGGING_BASE_DIR = "logs"          # Carpeta raíz de logs operativos
LOGGING_FILE_SIZE = 10485760       # Tamaño máximo por archivo (10 MB)
LOGGING_BACKUP_COUNT = 5           # Cantidad de históricos a mantener
LOGGING_QUEUE_MAX_SIZE = 10000     # Capacidad máxima del buffer en memoria
LOGGING_QUEUE_STRATEGY = "lossy"   # Desborde: 'lossy' (descarte) o 'lossless' (bloqueo)

# Configuración de Telemetría (Events)
EVENT_BASE_DIR = "events"          # Carpeta raíz de eventos binarios
EVENT_FILE_SIZE = 52428800         # Tamaño máximo por archivo de evento (50 MB)
EVENT_QUEUE_MAX_SIZE = 20000       # Capacidad máxima del buffer en memoria
EVENT_QUEUE_STRATEGY = "lossless"  # Desborde: 'lossless' (bloqueo para no perder datos)
```

---

## 📈 Rendimiento & Benchmarks Concurrentes

En las pruebas de estrés bajo concurrencia extrema (lanzando múltiples hilos escribiendo ráfagas continuas de datos):

*   **Rendimiento del Hilo Cliente**: **0.0045 ms (4.5 microsegundos)** en promedio por llamada de log/evento, permitiendo que tu hilo de ejecución principal continúe al 100% de su velocidad de procesamiento.
*   **Estabilidad de Recursos**: Los hilos activos del proceso se mantienen planos y estables durante la ráfaga (exactamente 1 hilo consumidor por canal de disco), absorbiendo de forma asíncrona la escritura física sin picos de CPU ni sobrecargas.
