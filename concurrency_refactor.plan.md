# Plan: Refactorización de Concurrencia a Bounded Queue y Worker Thread (LoggerBuf)

Este plan detalla la reestructuración del motor de concurrencia y la serialización en `LoggerBuf` para eliminar la creación de hilos ad-hoc, resolver el cuello de botella del stack walking (`inspect`) y optimizar el rollover de archivos.

## Tareas

- [ ] **Fase 1: Refactorización de `debulogger.py` (Logs de Diagnóstico)**
  - [ ] Eliminar el uso del módulo `inspect` y el stack walking manual en el hilo del cliente.
  - [ ] Adaptar el formato de log estándar de Python para capturar de manera nativa y optimizada el archivo, línea y función.
  - [ ] Implementar el patrón `QueueHandler` y `QueueListener` para que toda la escritura de logs operativos ocurra en un solo hilo de fondo dedicado.
- [ ] **Fase 2: Refactorización de `eventlogger.py` (Eventos de Telemetría)**
  - [ ] Crear un trabajador en segundo plano (`BackgroundEventWriter`) con una cola acotada (`queue.Queue(maxsize=10000)`).
  - [ ] Resolver el bug de bytes binarios en loggers de texto:
    - [ ] Proponer e implementar la serialización limpia a **JSON-Lines (JSONL)** como opción recomendada por su compatibilidad analítica directa.
    - [ ] Opcionalmente, dar soporte a escritura binaria pura usando **Length-Prefixed Framing** (longitud de 4 bytes + bytes serializados).
  - [ ] Desacoplar completamente el hilo del cliente: `create_event` encolará la tarea en microsegundos y retornará inmediatamente.
- [ ] **Fase 3: Optimización de Rollover y Memoria**
  - [ ] Reescribir `LoggingUtils.get_date_last_record` para usar un lector de cola eficiente (`seek(0, SEEK_END)`) en lugar de `f.readlines()`.
  - [ ] Evitar lecturas masivas de archivos de logs en memoria RAM.
- [ ] **Fase 4: Pruebas y Verificación**
  - [ ] Ejecutar el cliente de prueba (`ExampleClientClass.py`) para verificar que los logs y eventos se graben de manera secuencial, sin pérdidas y de forma asíncrona.
  - [ ] Medir el rendimiento bajo alta concurrencia y comprobar la estabilidad de memoria.
