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

### 2. Eventos Analíticos (Telemetría)
La telemetría usa Protobuf. Cada evento que rastrees debe ser categorizado usando tus enums personalizados de `EventTypes` y `Status` para asegurar consistencia en toda tu organización. Al igual que el debugger, la Telemetría inyecta automáticamente marcas de tiempo y cabeceras de enrutamiento tras bambalinas.

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

Aunque el inicio de "Cero Configuración" es genial para arrancar rápido, los desarrolladores avanzados necesitan control absoluto. `LoggerBuf` no te encierra. Puedes personalizar profundamente los tamaños de rotación, las colas de memoria y las rutas de forma global o por instancia.

**1. Por Defecto Globales (`settings_globals.py`)**
Ajusta las restricciones centrales del motor:
```python
LOGGING_FILE_SIZE = 10485760       # Tamaño máximo por archivo (10 MB)
LOGGING_QUEUE_MAX_SIZE = 10000     # Capacidad de la cola en memoria
LOGGING_QUEUE_STRATEGY = "lossy"   # Comportamiento de desborde
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
| `loggerbuf deprecate-subfield` | Depreca un campo de forma segura sin romper datos históricos. |
| `loggerbuf build` | Ejecuta el Schema Linter y compila los `.proto` a Python. |
| `loggerbuf decode-logs <File>` | Decodifica logs binarios a la Terminal o a formato JSONL. |

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
