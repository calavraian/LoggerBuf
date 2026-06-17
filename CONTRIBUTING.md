# Contributing to LoggerBuf 🚀

¡Gracias por tu interés en contribuir a LoggerBuf! 

Este documento establece las reglas y el flujo de trabajo oficial para cualquier colaborador del proyecto, **incluyendo asistentes de Inteligencia Artificial (IA)** y desarrolladores humanos. Seguir estas directrices asegura que el código mantenga su alta calidad, que las revisiones sean eficientes y que la cobertura de pruebas se mantenga robusta.

---

## 🛠️ Regla General del Entorno de Trabajo

Antes de ejecutar cualquier comando, ten en cuenta la siguiente política sobre el entorno de ejecución:
- **Uso de Entornos Virtuales:** Si el proyecto cuenta con un entorno virtual (como la carpeta `venv/`, `.venv/` o similar), **debes usarlo siempre** para cualquier operación. Esto incluye ejecutar `pip`, `python`, `pytest` o correr la herramienta CLI de `loggerbuf`. 
- Si no existe un entorno virtual en el proyecto, puedes proceder a utilizar el entorno global del sistema de forma precavida.

---

## 🔄 Flujo de Trabajo y Comunicación Base

Toda contribución y comunicación sobre nuevas características o resolución de bugs debe seguir estos pasos fundamentales:

1. **Observación o Comentario:** El usuario o desarrollador principal proporcionará la observación, reporte de bug o requerimiento.
2. **Análisis y Validación:** El colaborador (o IA) deberá analizar la petición y responder con sus observaciones, validaciones técnicas y viabilidad del cambio. **Importante:** No se debe ejecutar ni escribir código inmediatamente en esta fase.
3. **Clasificación del Cambio:** Basados en el análisis, se determinará si es un "Cambio Menor" o un "Cambio Complejo" para definir el protocolo de ejecución.

---

## ⚡ Protocolo para Cambios Menores

Se considera un cambio menor a ajustes pequeños, correcciones de redacción, adición de pruebas unitarias menores o parches que no modifiquen la arquitectura central.

Si ambas partes están de acuerdo y el cambio se clasifica como menor:
- Puedes ejecutar el código y aplicarlo **directamente a la rama `main`** del repositorio.
- No es necesario elaborar un plan de trabajo detallado previo a la ejecución.

---

## 🏗️ Protocolo para Cambios Complejos

Cualquier adición de nuevas características, refactorización significativa o cambios en la arquitectura entran en esta categoría. Requieren un control estricto:

1. **Plan de Trabajo:** Antes de tocar el código, el colaborador debe elaborar un plan de trabajo detallado (arquitectura, archivos afectados, enfoque) y presentarlo para recibir anotaciones y la **aprobación explícita** del desarrollador principal.
2. **Creación de Rama (Branch):** Una vez aprobado el plan, es **obligatorio** generar una nueva rama (branch) de trabajo específica para este ajuste (ej. `feature/nuevo-comando`, `fix/issue-memoria`).
3. **Commits Pequeños y Modulares:** Queda estrictamente prohibido agrupar múltiples conceptos en un solo commit gigante. Debes hacer una serie de commits pequeños, atómicos y modulares que reflejen el progreso paso a paso.
4. **Pruebas y Cobertura:** Asegúrate de escribir las pruebas unitarias correspondientes o de ajustar las existentes que hayan sido afectadas. La meta obligatoria es **mantener un porcentaje de cobertura de código entre 80% y 85% (o superior)**.
5. **Documentación:** Si el cambio introduce nuevos comandos, arquitecturas o flujos, es obligatorio ajustar los archivos `README.md` (Inglés) y `README.es.md` (Español) para reflejar estas actualizaciones.
6. **Revisión en el Forgejo/Git:** Una vez completado el desarrollo en la rama, súbela al servidor (ej. Forgejo / GitHub) para poder evaluar y realizar una revisión de código formal.
7. **Merge:** Solo se realizará el merge hacia `main` cuando el desarrollador principal dé "luz verde" tras la revisión, o en su defecto, solicitará ajustes adicionales en la misma rama.
