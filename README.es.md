# LoggerBuf 🚀

🇺🇸 [English](README.md) | 🇪🇸 Español

### *Structured Telemetry & High-Performance Async Logger for Python*

`LoggerBuf` es una biblioteca de logging híbrida y de alto rendimiento diseñada para resolver un problema clásico: **la separación limpia entre logs operativos de diagnóstico (debug) y eventos de telemetría de negocio estructurados**.

A diferencia de las herramientas de logging tradicionales de texto plano que colapsan y corrompen datos bajo presión, la implementación nativa de **Protocol Buffers** en `LoggerBuf` garantiza esquemas de datos ultra rápidos, estables y compactos. Tu información se guarda en archivos binarios optimizados con rotación automática y compresión Gzip, asegurando cero interferencia con el rendimiento de tu aplicación principal.

---

## 🤔 ¿Por qué LoggerBuf? (El Problema y la Solución)

**El Problema:** 
Configurar el módulo nativo `logging` de Python para producción es notoriamente complejo. Si quieres escritura asíncrona, rotación automática de archivos y compresión, terminas escribiendo cientos de líneas de código repetitivo. Peor aún, los desarrolladores suelen mezclar errores operativos ("Fallo al conectar a la BD") con analíticas de negocio ("Usuario completó la compra") en los mismos archivos de texto gigantes, haciendo que la extracción de datos sea una pesadilla.

**La Solución:**
`LoggerBuf` resuelve esto ofreciendo una arquitectura de doble canal lista para usar (*out of the box*), otorgándote información extra "gratis" para un rastreo y depuración superior:
1.  **Debugger**: Para logs operativos (texto legible). Inyecta automáticamente el archivo, clase y número de línea exactos en cada log sin la lentitud mágica del módulo `inspect`.
2.  **Telemetry**: Para analíticas de negocio. Utiliza Protocol Buffers binarios para garantizar que tus datos estén siempre estructurados, fuertemente tipados y listos para ingestas masivas en bases de datos.

**El "Súper Poder" (Cero Configuración):**
Con solo dos líneas de código, obtienes un logger de grado industrial, no bloqueante y auto-rotativo:

```python
import loggerbuf

# ¡Boom! Ya tienes un logger rápido, asíncrono y auto-rotativo con contexto gratis.
log = loggerbuf.create_debugger(name="MAIN_APP")
log.info("Aplicación iniciada de forma segura.")
```

---

## ⚙️ Características Internas (El Motor Técnico)

*   **⚡ Hilo de Fondo Asíncrono**: Encolar un log toma un promedio de **0.004 ms**. Un *worker* de fondo dedicado hace el trabajo pesado de escribir en disco, asegurando que tu aplicación principal nunca se bloquee.
*   **📦 Rotación Automática y Compresión**: Los archivos rotan automáticamente cuando alcanzan un límite de tamaño (ej. 10MB) y los archivos históricos se comprimen usando Gzip en segundo plano para ahorrar espacio en disco.
*   **🛡️ Perfiles de Desborde Configurables**:
    *   `LOSSLESS` (Telemetría): Bloquea brevemente si la cola está llena, garantizando que no se pierda ni un solo evento analítico.
    *   `LOSSY` (Debugger): Descarta silenciosamente los logs más antiguos si el disco está saturado, protegiendo el rendimiento de tu app durante ráfagas extremas.

---

## 🏢 Características Empresariales de Depuración

LoggerBuf provee herramientas avanzadas que te permiten ajustar la salida del depurador en tiempo real, sin reiniciar tu aplicación.

### 1. Filtrado Dinámico de Consola
Puedes configurar qué ver en consola dinámicamente mediante `loggerbuf.json`:
- `LOGGING_CONSOLE_ENABLED`: Activa o desactiva la salida de consola (`true`/`false`).
- `LOGGING_CONSOLE_ALLOWED_CLASSES`: Lista de clases a mostrar (ej. `["PaymentService"]`).
- `LOGGING_CONSOLE_ALLOWED_LEVELS`: Lista de niveles a mostrar (ej. `["ERROR"]`).

### 2. Metadatos Configurables
Controla qué campos de rastreo (timestamp, archivo, clase, línea) se guardan usando `LOGGING_METADATA` en tu configuración.

### 3. Destino y Persistencia (History On/Off)
Tienes control absoluto sobre dónde van tus logs. La persistencia en disco no es forzosa. Configura `LOGGING_DESTINATION` con 5 modos:
- `CONSOLE`: Historial APAGADO. Imprime solo a la terminal. Ideal para desarrollo local.
- `JSON`: Historial ENCENDIDO. Escribe JSON estructurado en disco.
- `GZIP`: Historial ENCENDIDO. Escribe directo a Gzip comprimido. Ideal para producción.
- `JSON_AND_CONSOLE`: Historial ENCENDIDO. Disco y terminal simultáneamente.
- `GZIP_AND_CONSOLE`: Historial ENCENDIDO. Gzip y terminal simultáneamente.
*(Si hay un error en tu configuración JSON, LoggerBuf degradará de forma segura a `CONSOLE` para evitar pérdida de trazas).*

### 4. Serialización de Objetos Complejos
Pasa diccionarios, listas u objetos personalizados. LoggerBuf los interceptará y los convertirá a JSON seguro, manteniendo tu código limpio.

---

## 💻 Guía Operativa (En las trincheras)

### 1. Logs Operativos de Diagnóstico (Debugger)
Usa el debugger para el monitoreo diario de tu aplicación (`debug`, `info`, `warning`, `error`, `critical`).

```python
class PaymentService:
    def process(self):
        log.info("Procesando pago de usuario...")
        try:
            # ... lógica de negocio ...
        except Exception as e:
            log.error(f"Fallo en transacción: {e}")
```
*Observa la "Información de Rastreo Gratis" enriquecida automáticamente en la salida:*
`[2026-05-29 10:15:30,123] >>MAIN_APP<< (payment.py::PaymentService::process->5) - *INFO* - message::>Procesando pago de usuario...`

**Entendiendo la Estructura de Salida:**
Nuestro formateador revela al instante el *dónde* y el *qué* de cualquier registro sin que pases contexto extra:
- `[Timestamp]`: Preciso al milisegundo.
- `>>NombreLogger<<`: Identifica qué módulo emitió el log (ej. `MAIN_APP`).
- `(archivo.py::Clase::metodo->linea)`: La ubicación exacta en el código. Nunca más adivines de dónde viene un error.
- `- *NIVEL* -`: La severidad (`INFO`, `ERROR`, etc.).
- `message::> [Payload]`: El mensaje real o el objeto JSON serializado.

### 2. Eventos Analíticos (Telemetría)
La Telemetría usa Protobuf. Cada evento que rastrees debe ser categorizado usando tus enums personalizados `EventType` y `EventStatus` para asegurar la consistencia. Al igual que el debugger, la Telemetría inyecta automáticamente las marcas de tiempo y el enrutamiento. tras bambalinas.

```python
from data_logs import main_data_pb2, event_status_pb2

telemetry = loggerbuf.create_telemetry()

# Crea tu evento estructurado
event = main_data_pb2.Event()
event.event_type = event_status_pb2.EventTypes.EVENT_DATA_BASE_PROCESSING
event.general_note = "Usuario registrado exitosamente"
event.status = event_status_pb2.Status.STATUS_COMPLETED

# Envíalo a la cola binaria asíncrona
telemetry.send(event)
```

---

## 🎛️ Control Total (Configuración Avanzada)

## 🎛️ Configuración Avanzada y Hot Reload

LoggerBuf se puede configurar globalmente mediante el archivo `loggerbuf.json` en tu directorio raíz. La forma más fácil de administrarlo es con el CLI:

```bash
loggerbuf config set LOGGING_FILE_SIZE 5000000
```

> [!TIP]
> **Hot Reload (Sin Reinicios)**
> Al cambiar el nivel de los logs (`loggerbuf config set LOG_LEVEL DEBUG`), el hilo de vigilancia en memoria detectará el cambio y elevará dinámicamente tu verbosidad **sin necesidad de reiniciar tu aplicación**. Otros cambios estructurales (como el tamaño de rotación) sí requerirán un reinicio.

### Telemetría Consolidada
Para la máxima eficiencia I/O, LoggerBuf genera un único archivo JSON para su salida de debug (`debug_logs_MAIN.log`). El nivel de información en este archivo dependerá de tu `LOG_LEVEL`. Puedes explorarlo fácilmente:
```bash
loggerbuf decode-debug logs/history/debug_logs_MAIN.log --grep "Error" --tail 50
```

**2. Sobrescritura por Instancia**
Puedes ignorar completamente los ajustes globales al momento de crear un logger:
```python
# Crea un logger especializado que rota cada 50MB y usa una cola segura (lossless)
custom_log = loggerbuf.create_debugger(
    name="CRITICAL_WORKER",
    max_bytes=52428800,
    queue_strategy="lossless"
)
```

---

## 🔧 El CLI (Tus Herramientas de Administración)

El CLI de LoggerBuf (`loggerbuf`) es el **ciudadano de primera clase** para gestionar tus esquemas de telemetría y decodificar tus archivos binarios.

| Comando | Descripción |
|---|---|
| `loggerbuf init` | Inicializa el directorio `data_logs/protos`. |
| `loggerbuf create-event <Name>` | Crea una plantilla `.proto` para un nuevo evento. |
| `loggerbuf register-event <Name>`| Vincula tu evento en el pipeline `main_data.proto`. |
| `loggerbuf add-subfield ...` | Inyecta de forma segura un nuevo campo en un evento existente. |
| `loggerbuf build` | Ejecuta el Schema Linter y compila los `.proto` a Python. |
| `loggerbuf config set <key> <value>` | Actualiza la configuración global. Ejemplo: `loggerbuf config set LOG_LEVEL DEBUG` |
| `loggerbuf config get <key>` | Consulta un valor de configuración global. |
| `loggerbuf decode-logs <File>` | Decodifica logs binarios de telemetría a Terminal o JSONL. |
| `loggerbuf event add-type <Name>` | Añade una nueva sub-clasificación `EventType` a tu proyecto. |
| `loggerbuf event add-status <Type> <Status>`| Añade un nuevo `EventStatus` bajo un `EventType` existente. |
| `loggerbuf decode-debug <File>`| Explora logs de debug históricos visualmente (soporta `--grep`, `--head`, `--tail`). |

### Ejemplos Potentes del CLI

**1. Decodificar Telemetría Binaria:**
Extrae miles de eventos binarios a un JSON legible en milisegundos.
```bash
# Imprime en formato JSON legible en la terminal
loggerbuf decode-logs logs/telemetry_queue.bin

# Decodifica directo a un archivo JSONL para bases de datos
loggerbuf decode-logs logs/telemetry_queue.bin --out output.jsonl
```

**2. Explorar el Historial de Depuración:**
Busca entre gigabytes de logs operativos (JSON o Gzip) sin esfuerzo usando el explorador integrado.
```bash
# Busca la palabra 'CRITICAL' en un archivo comprimido y muestra los últimos 20
loggerbuf decode-debug logs/history/debug_logs.gz --grep "CRITICAL" --tail 20

# Ve los primeros 50 logs de un archivo JSON estándar
loggerbuf decode-debug logs/history/debug_logs.json --head 50
```

### Sub-clasificación de Eventos (EventType y EventStatus)
Para lograr analíticas granulares, LoggerBuf te permite definir una jerarquía de sub-clasificaciones (**EventType**) y sus respectivos estados (**EventStatus**). 
**Nota:** Usar tipos y estados personalizados es completamente opcional. Siempre puedes usar los estados globales por defecto (ej. `STATUS_PENDING`, `STATUS_COMPLETED`) para cualquier evento si prefieres mantenerlo simple.

```bash
# Añade un nuevo EventType para red, junto con dos estados.
loggerbuf event add-type NETWORK --statuses STARTED,FAILED

# Más adelante, añade un nuevo estado al tipo NETWORK
loggerbuf event add-status NETWORK TIMEOUT

# Lista tus tipos y estados registrados
loggerbuf event list
```
*¡No olvides ejecutar `loggerbuf build` para compilar los cambios hechos por estos comandos!*

### 🛡️ Evolución de Esquemas (Las Reglas de Oro)
Debido a que la telemetría se almacena en binario, **nunca debes eliminar un campo ni cambiar su tipo de dato**.
`loggerbuf build` incluye un **Schema Linter** que compara tus archivos con una instantánea histórica y bloquea cualquier cambio destructivo.

Si necesitas cambiar un campo, usa el CLI para deprecar el antiguo y agregar uno nuevo de forma segura:
```bash
loggerbuf deprecate-subfield UserEvent "edad"
loggerbuf add-subfield UserEvent "edad_str" "string"
loggerbuf build
```

---

## 🧠 Bajo el Capó: El Mito del "Proto Gigante"

Notarás que `main_data.proto` actúa como un envoltorio gigante que contiene *absolutamente todos los eventos* que tu sistema puede emitir.

**¿Significa esto que cada log pesa una tonelada? ¡No!**
Protobuf es extremadamente eficiente. Los campos no poblados ocupan **cero bytes** en el disco. Incluso si tu esquema tiene 500 eventos diferentes registrados, una entrada de log serializada solo consumirá los bytes exactos del único evento que realmente llenaste.
