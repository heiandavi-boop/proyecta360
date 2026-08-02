# Proyecta360 — MVP funcional completo v2.1

MVP web para gestión integral de proyectos híbridos, con gobierno PMP, ejecución por componentes, Scrum/Kanban, Gantt, riesgos, entregables, evidencias, historial, exportación y una capa IA-ready conectada al estado real del proyecto.

## Qué incluye esta versión

- Backend en Python con FastAPI.
- Base de datos SQLite local, creada automáticamente al iniciar.
- Frontend web funcional en HTML, CSS y JavaScript.
- Login básico por roles para demo.
- Portafolio ejecutivo en tabla filtrable, con botón Abrir por proyecto.
- Parametrización del proyecto.
- Componentes con metodología propia: Tradicional, Scrum, Kanban o Híbrida.
- Gantt con creación de tareas: tareas resumen, tareas hijas, sangría, duración, hitos, predecesoras, tipos de dependencia FS/SS/FF/SF, lag y fecha fin calculada automáticamente.
- Scrum board con historias, puntos, estados y burndown básico.
- Riesgos con probabilidad, impacto, nivel, responsable, estrategia, plan de mitigación y plan de contingencia.
- Recursos / responsables con capacidad.
- Entregables y productos de conocimiento.
- Carga real de evidencias y descarga de archivos.
- Historial de cambios.
- Conversaciones internas por proyecto, componente, actividad, riesgo o entregable.
- Dashboard ejecutivo e inteligencia del proyecto.
- Exportación real del proyecto en JSON.
- Reporte ejecutivo descargable en HTML.
- Chat IA-ready conectado a métricas, riesgos, hitos, entregables, evidencias y presupuesto del proyecto.
- Pruebas automáticas con pytest.

## Usuarios iniciales

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | admin@proyecta360.local | Definir con `PROYECTA360_ADMIN_PASSWORD` |
| Project Manager | alejandra@proyecta360.ai | Definir con `PROYECTA360_PM_PASSWORD` |
| Consulta | consulta@proyecta360.local | Definir con `PROYECTA360_READONLY_PASSWORD` |

> El login es básico para MVP/demo. Para producción se debe reemplazar por autenticación robusta con contraseñas seguras, expiración de sesión y permisos por endpoint.

## Cómo ejecutar en Windows PowerShell

Desde la carpeta del proyecto:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Luego abre:

```text
http://127.0.0.1:8000
```

También puedes usar:

```powershell
.\iniciar.ps1
```

## Estructura limpia del proyecto

```text
proyecta360_ai_project/
├── app.py
├── iniciar.ps1
├── requirements.txt
├── README.md
├── static/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── favicon.svg
└── tests/
    └── test_api.py
```

Al ejecutar por primera vez se crean automáticamente:

```text
proyecta360.db
uploads/
```

## Endpoints principales

```text
GET  /api/health
GET  /api/bootstrap
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
POST /api/projects
PUT  /api/projects/{project_id}
POST /api/tasks
PUT  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
POST /api/tasks/{task_id}/indent
POST /api/tasks/{task_id}/outdent
POST /api/tasks/{task_id}/toggle
GET  /api/portfolio
POST /api/dependencies
DELETE /api/dependencies/{dependency_id}
POST /api/sprints
POST /api/stories
PUT  /api/stories/{story_id}
POST /api/risks
POST /api/resources
POST /api/components
POST /api/deliverables
POST /api/evidences/upload
GET  /api/evidences/{evidence_id}/download
POST /api/conversations
POST /api/conversations/{thread_id}/messages
GET  /api/projects/{project_id}/metrics
GET  /api/projects/{project_id}/intelligence
GET  /api/projects/{project_id}/export/json
GET  /api/projects/{project_id}/export/html
POST /api/ai/generate-plan
POST /api/ai/report
POST /api/ai/chat
```

## Pruebas

```powershell
python -m pytest -q
```

Resultado esperado:

```text
13 passed
```


## Cambios clave v2.1 según validación con stakeholder

- La pantalla Portafolio se simplificó a una tabla ejecutiva filtrable para evitar entrar proyecto por proyecto.
- La fecha fin del proyecto queda calculada por cronograma; el usuario solo define fecha inicio y, opcionalmente, fecha compromiso contractual.
- La moneda se selecciona desde catálogo controlado.
- El campo fase y el orden manual dejan de ser campos centrales en la creación de tareas.
- Las tareas se crean con lógica de cronograma: duración, predecesora, tipo de dependencia y jerarquía por sangría.
- Las tareas resumen calculan inicio, fin, duración y avance con base en sus tareas hijas.

## Notas técnicas

- La IA actual es determinística y no consume llaves externas; está conectada al estado real del proyecto.
- La arquitectura queda lista para sustituir la capa `/api/ai/*` por OpenAI o Azure OpenAI.
- Para producción se recomienda migrar SQLite a PostgreSQL y agregar pgvector para documentos, evidencias y RAG.
- La colaboración en tiempo real aún no usa WebSockets; las conversaciones sí centralizan acuerdos y decisiones.
