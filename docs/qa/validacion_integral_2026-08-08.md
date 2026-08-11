# Reporte de Validacion PRUNIN

Fecha: 2026-08-08  
Alcance: backend FastAPI, frontend React/TypeScript, flujos UI, endpoints, datos, roles, CSV, IA y consistencia visual.

## 1. Resumen ejecutivo

- Estado general del proyecto: funcional en los modulos principales, con build y pruebas automaticas pasando.
- Nivel de estabilidad: medio-alto para demo guiada con usuario administrador.
- Riesgo de demo: medio. Hay riesgos en importacion CSV repetida, permisos visuales para usuario de consulta y trazabilidad importada Scrum -> Plan Maestro.
- Recomendacion final: no listo para demo ejecutiva sin restricciones. Si se hace demo controlada, evitar reimportar el mismo CSV y usar rol administrador/PM.

## 2. Validaciones ejecutadas

| Modulo | Flujo probado | Resultado | Observaciones |
|---|---|---|---|
| Login | Login invalido y login admin | OK | Mensaje de credenciales invalidas visible. El 401 es esperado en esta prueba. |
| Portafolio | Carga, filtro, empty state, abrir proyecto, crear/importar | OK con correccion | Se corrigio crear proyecto con campos vacios y empty state. |
| Plan Maestro / Gantt | Carga tareas, crear tarea, crear hito, vincular dependencia, menu fila | OK | Acciones principales visibles y funcionales. |
| Scrum | Carga tablero, crear historia, selector de tarea Plan Maestro, crear estado | OK | Trazabilidad manual visible desde Scrum. |
| Recursos | Crear recurso y verlo en tabla | OK | Sin errores de consola/red. |
| Riesgos | Crear riesgo con mitigacion y contingencia | OK | Planes separados visibles. |
| Conversar | Crear hilo y enviar mensaje | OK | Mensaje persistente en UI. |
| Conocimiento | Crear componente, producto y subir evidencia | OK | Evidencia visible con archivo cargado. |
| IA del Proyecto | Secciones IA, tabla, modal, claves tecnicas, gate de aplicar | OK parcial | Backend bloquea aplicar sin aprobar; tabla no muestra claves tecnicas. |
| CSV | Importar sample, errores invalidos, reimportar | Parcial | Importa, pero reimporta duplicando y sample completo no vincula HU a tareas. |
| Permisos | Rol Consulta lectura y mutacion via API | Parcial | Backend bloquea mutaciones; UI aun muestra accion de crear proyecto. |
| Responsive | 390x844 y 1366x768 | Parcial | Sin overflow global; sidebar mobile ocupa alto relevante. |

## 3. Hallazgos criticos

| ID | Modulo | Problema | Impacto | Evidencia | Accion tomada o recomendada |
|---|---|---|---|---|---|
| CR-001 | CSV / Scrum | El sample `proyecto_importacion_completa_demo.csv` importa historias Scrum sin vincularlas al Plan Maestro. | Incumple el criterio de trazabilidad Scrum -> Plan Maestro para importacion completa. | Import API: `stories=2`, `linked=0`. | Recomendado: agregar `master_task_wbs` o `master_task_id` al sample y validar en importacion. |

## 4. Hallazgos medios

| ID | Modulo | Problema | Impacto | Evidencia | Accion tomada o recomendada |
|---|---|---|---|---|---|
| MD-001 | CSV | Reimportar el mismo CSV duplica proyectos con el mismo nombre. | Puede ensuciar demos, KPIs y portafolio. | Reimport sample: nombre `Proyecto Demo Importado` aparece 3 veces. | Recomendado: idempotencia por `import_id`/nombre o advertencia de duplicado. |
| MD-002 | Permisos UI | El rol Consulta ve `+ Nuevo proyecto`, aunque backend responde 403. | Confusion de usuario y mala percepcion de permisos. | UI con `consulta@prunin.local` muestra accion visible. | Recomendado: ocultar o deshabilitar acciones de escritura por rol. |
| MD-003 | Plan Maestro | KPI de ruta critica muestra cantidad, pero la tabla no identifica explicitamente esas tareas. | Usuario no sabe que tareas forman la ruta critica. | `metrics.critical_path_tasks=9`; payload de tareas no expone marca visual equivalente. | Recomendado: exponer `is_critical` o resaltar por dependencias calculadas. |
| MD-004 | IA | Clic en `Aplicar` detras del modal queda interceptado por el modal abierto. | Interaccion confusa si el usuario intenta operar tabla con modal abierto. | Playwright: `modal-backdrop intercepts pointer events`. | Aceptable si se opera desde modal; recomendado cerrar modal o usar solo acciones dentro del modal. |

## 5. Hallazgos menores

| ID | Modulo | Problema | Impacto | Evidencia | Accion tomada o recomendada |
|---|---|---|---|---|---|
| MN-001 | Responsive | Sidebar mobile ocupa aprox. 448px de alto antes del contenido. | Menor eficiencia en pantallas pequenas. | Medicion mobile 390x844. | Recomendado: menu colapsable/hamburguesa. |
| MN-002 | Portafolio | Tabla podia cortar columnas cuando el contenedor ocultaba overflow horizontal. | Boton `Abrir` y fechas podian verse recortados. | Revision visual previa y CSS `.table-scroll`. | Corregido: `overflow-x: auto`. |
| MN-003 | Portafolio | Filtro sin resultados no mostraba estado vacio claro. | Usuario podia pensar que la tabla fallo. | Filtro `zzzz-no-existe`. | Corregido: fila `Sin datos`. |

## 6. Botones validados

| Modulo | Boton | Accion esperada | Resultado | Endpoint usado si aplica |
|---|---|---|---|---|
| Auth | Ingresar | Autenticar usuario | OK | `POST /api/auth/login` |
| TopBar | Salir | Cerrar sesion | OK | `POST /api/auth/logout` |
| Portafolio | + Nuevo proyecto | Abrir panel crear/importar | OK | UI local |
| Portafolio | Crear proyecto | Crear solo con campos requeridos | OK corregido | `POST /api/projects` |
| Portafolio | Importar | Deshabilitado sin archivo; importa con CSV | OK parcial | `POST /api/projects/import/csv` |
| Portafolio | Abrir | Cambiar proyecto y abrir Plan Maestro | OK | `GET /api/bootstrap?project_id=` |
| Plan Maestro | + Tarea | Crear tarea | OK | `POST /api/tasks` |
| Plan Maestro | + Hito | Crear hito | OK | `POST /api/tasks` |
| Plan Maestro | Vincular | Crear dependencia entre filas | OK | `POST /api/dependencies` |
| Plan Maestro | Recalcular cronograma | Actualizar cronograma | OK | `PUT /api/tasks/{task_id}` |
| Plan Maestro | Menu fila | Indentar, desindentar, subtarea, editar, eliminar, vincular Scrum | OK visual | Varios `/api/tasks/*`, `/api/stories` |
| Scrum | Nueva historia | Crear historia | OK | `POST /api/stories` |
| Scrum | Crear estado | Agregar columna local | OK | LocalStorage |
| Recursos | + Recurso | Crear recurso | OK | `POST /api/resources` |
| Riesgos | + Riesgo | Crear riesgo | OK | `POST /api/risks` |
| Conversar | + Hilo | Crear conversacion | OK | `POST /api/conversations` |
| Conversar | Enviar mensaje | Agregar mensaje | OK | `POST /api/conversations/{thread_id}/messages` |
| Conocimiento | + Componente | Crear componente | OK | `POST /api/components` |
| Conocimiento | + Producto | Crear entregable/producto | OK | `POST /api/deliverables` |
| Conocimiento | + Evidencia | Subir evidencia | OK | `POST /api/evidences/upload` |
| IA | Ver | Abrir detalle recomendacion | OK | UI local |
| IA | Aprobar/Rechazar/Aplicar | Gestionar recomendacion | OK API, UI parcial | `/api/ai/recommendations/{id}/*` |

## 7. Campos validados

| Modulo | Campo | Fuente de datos | Valor esperado | Resultado |
|---|---|---|---|---|
| Login | Correo/password | Usuario demo | Credenciales validas/invalidas | OK |
| Portafolio | Busqueda | `data.portfolio` | Filtra por nombre/PM/metodologia | OK |
| Portafolio | Estado | `health/status` | Filtra estados | OK basico |
| Portafolio | Nombre/PM/Sponsor | Formulario manual | Obligatorios | OK corregido |
| Portafolio | Archivo CSV | File input | Requerido para importar | OK |
| Plan Maestro | Nombre, inicio, duracion, responsable, avance, tipo | `tasks/resources` | Crear tarea/hito | OK |
| Scrum | Titulo, sprint, estado, puntos, responsable, prioridad, tarea Plan Maestro | `stories/sprints/tasks` | Crear HU vinculable | OK |
| Riesgos | Riesgo, probabilidad, impacto, mitigacion, contingencia, owner | `risks/resources` | Datos visibles separados | OK |
| Recursos | Nombre, rol, email, capacidad | `resources` | Crear y listar | OK |
| Conversar | Titulo, tipo, autor, mensaje | `conversation_threads/messages` | Crear hilo/mensaje | OK |
| Conocimiento | Componente, producto, evidencia | `components/deliverables/evidences` | Crear/subir/listar | OK |
| IA | Justificacion, impacto, riesgo, prioridad, estado | `recommendations` | Labels funcionales, no claves tecnicas | OK |

## 8. Endpoints validados

| Metodo | Endpoint | Usado por | Resultado | Observaciones |
|---|---|---|---|---|
| GET | `/api/health` | Health check | OK | 200 |
| POST | `/api/auth/login` | Login | OK | 200 y 401 esperado |
| POST | `/api/auth/logout` | Logout | OK | 200 |
| GET | `/api/bootstrap` | Carga inicial | OK | Requiere token |
| GET | `/api/i18n/languages` | Idiomas | OK | 200 |
| GET | `/api/i18n/catalog/es` | Catalogo | OK | 200 |
| GET | `/api/portfolio` | Portafolio | OK | 200 |
| POST | `/api/projects` | Crear proyecto | OK | 403 para Consulta |
| POST | `/api/projects/import/csv` | Import CSV | Parcial | Duplica en reimportacion |
| GET | `/api/projects/{id}/metrics` | KPIs | OK | 200 |
| GET | `/api/projects/{id}/intelligence` | IA/KPIs | OK | 200 |
| GET | `/api/projects/{id}/scrum/linkable-tasks` | Scrum linkage | OK | 200 |
| GET | `/api/projects/{id}/tasks/{task_id}/scrum-summary` | Trazabilidad | OK | 200 |
| POST | `/api/tasks` | Crear tarea/hito | OK | 403 para Consulta |
| PUT | `/api/tasks/{task_id}` | Editar/recalcular | OK | 200 en flujos |
| DELETE | `/api/tasks/{task_id}` | Eliminar | No validado destructivo UI | Requiere confirmacion |
| POST | `/api/dependencies` | Vincular tareas | OK | 200 |
| POST | `/api/stories` | Crear historia | OK | 200 |
| PUT | `/api/stories/{story_id}` | Mover/vincular historia | OK API cubierto por tests |
| POST | `/api/resources` | Crear recurso | OK | 200 |
| POST | `/api/risks` | Crear riesgo | OK | 200 |
| POST | `/api/conversations` | Crear hilo | OK | 200 |
| POST | `/api/conversations/{thread_id}/messages` | Enviar mensaje | OK | 200 |
| POST | `/api/components` | Crear componente | OK | 200 |
| POST | `/api/deliverables` | Crear producto | OK | 200 |
| POST | `/api/evidences/upload` | Subir evidencia | OK | 200 |
| GET | `/api/projects/{id}/ai/recommendations` | IA | OK | 200 |
| GET | `/api/projects/{id}/ai/history` | IA historial | OK | 200 |
| POST | `/api/projects/{id}/ai/analyze` | Analizar proyecto | OK en tests/API previos | No reejecutado largo en UI final |
| POST | `/api/ai/recommendations/{id}/apply` | Aplicar recomendacion | OK gate | 400 si no esta aprobada |
| POST | `/api/ai/recommendations/{id}/approve` | Aprobar | OK tests/API | 200 |
| POST | `/api/ai/recommendations/{id}/reject` | Rechazar | OK tests/API | 200 |

## 9. Pruebas automaticas

| Comando | Resultado |
|---|---|
| `npm run typecheck` | OK |
| `npm run build` | OK |
| `python -m pytest -q` | OK, 68 passed |

Validacion focal post-correccion:

| Prueba | Resultado |
|---|---|
| Empty state de portafolio filtrado | OK |
| Crear proyecto deshabilitado con campos vacios | OK |
| Tabla con `overflow-x: auto` | OK |

## 10. Recomendacion final

No marcar como estable todavia para demo ejecutiva abierta. El producto esta fuerte para una demo guiada, pero faltan estos cierres antes de declararlo listo:

1. Hacer idempotente la importacion CSV o mostrar advertencia/bloqueo de duplicado.
2. Ajustar el CSV demo para incluir `master_task_wbs` o `master_task_id` y demostrar trazabilidad Scrum -> Plan Maestro desde importacion.
3. Ocultar/deshabilitar acciones de escritura para rol Consulta en frontend.
4. Exponer visualmente que tareas pertenecen a la ruta critica.
5. Considerar sidebar mobile colapsable.

Correcciones aplicadas en esta validacion:

- Portafolio: crear proyecto ya no se permite con nombre/PM/sponsor vacios.
- Portafolio: se agrego empty state `Sin datos`.
- Tablas: se habilito scroll horizontal para evitar columnas cortadas.

