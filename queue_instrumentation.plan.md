# Plan: Instrumentación y Telemetría de Colas (LoggerBuf Observability)

Este plan detalla el diseño e implementación de un sistema de métricas de alta precisión y seguro frente a concurrencia (thread-safe) para monitorear el comportamiento de las colas asíncronas y los trabajadores de `LoggerBuf`.

## Tareas

- [ ] **Fase 1: Diseñar el Recolector de Métricas (`QueueMetrics`)**
  - [ ] Crear la clase thread-safe `QueueMetrics` para capturar:
    - [ ] Pico máximo de elementos encolados (`peak_size`).
    - [ ] Total de elementos encolados y procesados.
    - [ ] Total de descartes por desborde (`drops`).
    - [ ] Número de veces que la cola quedó vacía (`empty_count`).
    - [ ] Tiempo mínimo, máximo y promedio de escritura en disco físico.
    - [ ] Tiempo total de vaciado o consumo de ráfagas (`total_drain_time`).
- [ ] **Fase 2: Integrar Instrumentación en `BackgroundEventWriter` (`eventlogger.py`)**
  - [ ] Añadir medición de tiempos mediante `time.perf_counter()` en el bucle del hilo trabajador.
  - [ ] Registrar incrementos y picos de cola en las operaciones de encolado y desencolado.
  - [ ] Exponer las métricas a través de la interfaz pública de `EventLogger`.
- [ ] **Fase 3: Actualizar Pruebas y Dashboard de Métricas**
  - [ ] Modificar `ExampleClientClass.py` para obtener el reporte de métricas tras la prueba de estrés concurrente.
  - [ ] Imprimir un panel visual (Dashboard) en consola mostrando estadísticas detalladas de performance y demostrando empíricamente la seguridad de los parámetros.
