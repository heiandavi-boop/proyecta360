Resumen de ajustes UX pre-demo

Objetivo: Aplicar mejoras de UX ligeras y no invasivas para aumentar la claridad y la adoptabilidad sin rediseñar.

Cambios realizados:
- Backend: Manejo amigable de errores de validación (RequestValidationError) en [proyecta360/app_factory.py](proyecta360/app_factory.py#L1-L240) para devolver mensajes en español y evitar exponer trazas internas.
- Frontend Master Plan: Añadido texto de ayuda en el formulario de creación de tareas indicando que la fecha de inicio se calcula automáticamente y mostrando la "Fecha base del proyecto" o el aviso de predecesora. Archivo: [frontend/src/features/masterPlan/MasterPlanView.tsx](frontend/src/features/masterPlan/MasterPlanView.tsx#L1-L240).
- Frontend AI: Añadida nota contextual en el Resumen Ejecutivo IA advirtiendo que las recomendaciones dependen de la disponibilidad de datos y pueden ser menos precisas si faltan evidencias. Archivo: [frontend/src/features/ai/AiView.tsx](frontend/src/features/ai/AiView.tsx#L1-L400).

Pruebas ejecutadas:
- Backend: Ejecutadas pruebas unitarias con `pytest` — 93 tests pasaron (ver historial anterior en transcripciones locales).
- Frontend: `npm run typecheck` y `npm run build` completados exitosamente.

Pendientes / Recomendados:
- Añadir tooltips en botones de Gantt y acciones rápidas para mejorar descubrimiento (siguiente iteración).
- Mostrar vínculo Scrum↔Plan Maestro con badges discretos en la lista Scrum y en la vista Gantt.
- Mejorar textos de las recomendaciones IA en la tabla/modal para sugerir pasos específicos y responsables.

Siguiente paso propuesto:
- Aplicar tooltips y badges pequeños en `MasterPlanView` y `ScrumView`, ejecutar typecheck/build y validar visualmente en entorno local.

Fecha: 2026-08-12
Autor: Equipo técnico (Copilot)
