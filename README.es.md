# LoggerBuf 🚀

🇺🇸 [English](README.md) | 🇪🇸 Español

### *Structured Telemetry & High-Performance Async Logger for Python*

`LoggerBuf` es una biblioteca de logging híbrida y de alto rendimiento diseñada para resolver un problema clásico: **la separación limpia entre logs operativos de diagnóstico (debug) y eventos de telemetría de negocio estructurados**.

A diferencia de los sistemas de logging tradicionales de texto plano, `LoggerBuf` utiliza **Protocol Buffers (Protobuf)** para garantizar esquemas de datos estables y compactos en su canal de telemetría. La información se guarda en archivos binarios optimizados con rotación automática y compresión Gzip, sin interferir jamás con el rendimiento de la aplicación principal.

---

## 🌟 Características Clave & Beneficios

*   **⚡ Concurrencia Desacoplada de Alta Velocidad**: Implementa el patrón *Productor-Consumidor* utilizando una cola acotada en memoria y un hilo de fondo dedicado. Los hilos de tu aplicación principal encolan logs en microsegundos (promedio de **0.004 ms**).
*   **🛡️ Estabilidad Garantizada**: Mantiene un control estricto de exactamente un solo hilo trabajador por canal, protegiendo al sistema operativo contra el agotamiento de hilos.
*   **📦 Telemetría Binaria Compacta**: Los eventos se graban en disco en formato binario puro, ocupando una fracción del espacio de un JSON tradicional.
*   **🛡️ Seguridad de Esquema Automatizada (Linter)**: Incluye un validador de esquemas que impide cambios destructivos accidentales en tus logs binarios históricos.
*   **🔧 CLI Profesional**: Una potente interfaz de línea de comandos (`loggerbuf`) basada en `click` para gestionar esquemas, decodificar logs y realizar pruebas de estrés.

---

## 🚀 Inicio Rápido

### 1. Instalación
Para instalar LoggerBuf y sus herramientas CLI globalmente (o en tu entorno virtual):
```bash
pip install -e .
```

### 2. El CLI de LoggerBuf: Tu Nuevo Superpoder
El CLI es el **ciudadano de primera clase** para interactuar con LoggerBuf. Automatiza la generación de código, previene errores manuales y decodifica tu telemetría.

| Comando | Descripción |
|---|---|
| `loggerbuf init` | Inicializa la carpeta `data_logs/protos` y el registro de esquemas. |
| `loggerbuf create-event <Name>` | Crea la plantilla de un archivo `.proto` para un nuevo evento. |
| `loggerbuf register-event <Name>`| Conecta tu evento personalizado a la estructura principal `main_data.proto`. |
| `loggerbuf add-subfield ...` | Inyecta de forma segura un nuevo campo en un evento existente. |
| `loggerbuf deprecate-subfield` | Depreca un campo antiguo sin romper la compatibilidad histórica. |
| `loggerbuf build` | Ejecuta el Linter de esquemas y compila los `.proto` a clases de Python. |
| `loggerbuf decode-logs <File>` | Decodifica archivos binarios `.log` a la terminal o a formato JSONL. |

> [!TIP]
> Siempre puedes ejecutar `loggerbuf --help` o `loggerbuf <comando> --help` para ver las instrucciones detalladas de uso.

### 3. Emitiendo Logs en Python

```python
import loggerbuf
from data_logs import main_data_pb2, event_status_pb2

# 1. Logs Operativos (Debugger)
log = loggerbuf.create_debugger(name="MAIN_APP")
log.info("Procesando pago de usuario...")
log.error("Fallo en transacción!")

# 2. Eventos Analíticos (Telemetría)
telemetry = loggerbuf.create_telemetry()

event = main_data_pb2.Event()
event.event_type = event_status_pb2.EventTypes.EVENT_DATA_BASE_PROCESSING
event.general_note = "Usuario registrado exitosamente"

# Encolado instantáneo no-bloqueante
telemetry.send(event)
```

---

## 🛡️ Evolución de Esquemas y Seguridad (Las Reglas de Oro)

Dado que LoggerBuf almacena la telemetría en **formato binario Protobuf**, modificar un esquema incorrectamente puede corromper permanentemente tu capacidad de leer datos históricos.

Para evitar esto, `loggerbuf build` ejecuta un **Schema Linter** que compara tus archivos `.proto` actuales contra una instantánea histórica (`.loggerbuf_schema_snapshot.json`).

> [!IMPORTANT]
> **La Regla de Oro:** Nunca elimines un campo, ni cambies su tipo de dato, ni modifiques su número de Tag (ej. `= 1;`).

Si necesitas "modificar" un campo, debes **deprecar el antiguo y crear uno nuevo**. El CLI automatiza esto de forma segura:

```bash
# 1. Deprecar el campo viejo (mantiene legibles los datos históricos)
loggerbuf deprecate-subfield UserEvent "edad"

# 2. Agregar el campo nuevo (el CLI calcula automáticamente el siguiente Tag ID disponible)
loggerbuf add-subfield UserEvent "edad_str" "string"

# 3. Recompilar
loggerbuf build
```

---

## 🧠 Bajo el Capó: El Mito del "Proto Gigante"

Notarás que `main_data.proto` actúa como un envoltorio gigante que contiene *absolutamente todos los eventos* que tu sistema puede emitir.

**¿Significa esto que cada log pesa una tonelada?**
¡No! Protobuf es extremadamente eficiente. Los campos no poblados (campos que no llenas explícitamente en Python) ocupan **cero bytes** en el disco.
Incluso si tu `main_data.proto` tiene 500 eventos diferentes registrados, una entrada de log serializada solo consumirá los bytes exactos del único evento que realmente poblaste. Esto permite que LoggerBuf sea infinitamente escalable sin desperdiciar espacio en disco.

---

## 🛠️ Configuración (`settings_globals.py`)

Puedes personalizar las características físicas del logger y los buffers en `settings_globals.py`:

```python
# Configuración de Telemetría (Events)
EVENT_BASE_DIR = "events"          # Carpeta raíz de eventos binarios
EVENT_FILE_SIZE = 52428800         # Tamaño máximo por archivo de evento (50 MB)
EVENT_QUEUE_MAX_SIZE = 20000       # Capacidad máxima del buffer en memoria
EVENT_QUEUE_STRATEGY = "lossless"  # Desborde: 'lossless' (bloqueo para no perder datos)
```
