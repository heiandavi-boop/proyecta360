# Proyecta360 — MVP funcional PMP + Scrum + IA-ready

Primera versión funcional de una herramienta de gestión de proyectos híbrida, inspirada en un modelo tipo Microsoft Project, pero preparada para combinar gobierno tradicional PMP con ejecución ágil Scrum/Kanban/XP.

## Qué incluye

- Backend en Python con FastAPI.
- Base de datos SQLite local.
- Frontend web tipo dashboard empresarial.
- Vista Gantt con actividades, hitos, responsables, avance y dependencias visuales.
- Módulo Scrum con tablero, sprint actual, puntos, avance y burndown básico.
- Gestión de riesgos con probabilidad, impacto, nivel y respuesta.
- Gestión de recursos y capacidad.
- Bloque de parametrización del proyecto:
  - Datos generales.
  - Modelo de control PMP + Scrum.
  - Metodologías permitidas.
  - Calendario laboral.
  - Fases.
  - Estados de actividades.
  - Estados Scrum.
  - Matriz de riesgo.
  - Gobierno del proyecto.
  - Parámetros IA.
- Endpoints IA-ready:
  - Generación automática de plan base.
  - Generación de informe ejecutivo.

> Nota: la capa de IA actual funciona de forma determinística para que el producto sea funcional sin llaves externas. Más adelante puede conectarse con OpenAI o Azure OpenAI reemplazando el bloque de `/api/ai/*`.

## Cómo ejecutar

### 1. Crear entorno virtual

```bash
python -m venv .venv
```

### 2. Activar entorno

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

Mac/Linux:

```bash
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación

```bash
uvicorn app:app --reload
```

### 5. Abrir en el navegador

```text
http://127.0.0.1:8000
```

## Estructura

```text
proyecta360_ai_project/
├── app.py                  # Backend FastAPI + SQLite + APIs
├── proyecta360.db           # Base de datos local, se crea automáticamente
├── requirements.txt
├── README.md
└── static/
    ├── index.html           # Frontend
    ├── styles.css           # Estilos tipo SaaS empresarial
    └── app.js               # Lógica de interfaz y consumo de API
```

## API principal

```text
GET  /api/bootstrap
GET  /api/health
POST /api/projects
PUT  /api/projects/{project_id}
POST /api/tasks
PUT  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
POST /api/dependencies
POST /api/stories
PUT  /api/stories/{story_id}
POST /api/risks
POST /api/resources
POST /api/ai/generate-plan
POST /api/ai/report
```

## Siguiente evolución recomendada

1. Separar backend en módulos: proyectos, tareas, scrum, riesgos, recursos, IA.
2. Migrar SQLite a PostgreSQL.
3. Agregar pgvector para documentos, actas, lecciones aprendidas y RAG.
4. Reemplazar frontend vanilla por Next.js + TypeScript para producto empresarial.
5. Integrar autenticación, roles y permisos.
6. Agregar importación desde Excel, Project o CSV.
7. Conectar OpenAI/Azure OpenAI para:
   - Generar cronogramas.
   - Sugerir dependencias.
   - Crear historias de usuario.
   - Identificar riesgos.
   - Generar reportes ejecutivos.
