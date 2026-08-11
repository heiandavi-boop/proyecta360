# PRUNIN

Plataforma para gestion integral de proyectos con enfoque hibrido PMP + Scrum, control de cronograma, riesgos, recursos, conversaciones, evidencias, productos de conocimiento y Motor IA interno.

## Arquitectura

```text
proyecta360_ai_project/
├── app.py
├── proyecta360/
│   ├── api/routes/
│   ├── core/
│   ├── schemas/
│   └── services/
├── frontend/
│   ├── src/
│   └── dist/
├── contracts/
│   └── api/
├── static/
│   ├── favicon.svg
│   └── i18n/
├── scripts/
└── tests/
```

## Lenguajes y tecnologias

- Python: backend FastAPI, servicios de dominio, seguridad, cronograma, Motor IA interno y persistencia.
- TypeScript + React: frontend principal.
- CSS: sistema visual del frontend.
- JSON: catalogos i18n y contratos.
- SQLite: base de datos local por defecto.
- PostgreSQL: base de datos operativa mediante `DATABASE_URL`.
- OpenAPI: contrato fuente para tipos del frontend.

## Ejecutar

Desde PowerShell:

```powershell
cd "C:\Users\atruj\OneDrive\Escritorio\Proyecto alejandra\proyecta360_mvp_v21_msproject\proyecta360_ai_project"
$env:Path='C:\Program Files\nodejs;' + $env:Path
cd frontend
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Abrir:

```text
http://127.0.0.1:8000
```

Modo desarrollo frontend:

```powershell
cd frontend
npm run dev
```

## Usuarios iniciales

| Rol | Correo | Password por defecto |
|---|---|---|
| Administrador | admin@prunin.local | admin123 |
| Project Manager | alejandra@prunin.ai | demo123 |
| Consulta | consulta@prunin.local | consulta123 |

Puedes sobreescribirlos con:

```text
PRUNIN_ADMIN_PASSWORD
PRUNIN_PM_PASSWORD
PRUNIN_READONLY_PASSWORD
```

## Configuracion

Copiar `.env.example` como referencia de variables:

```text
APP_ENV
SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES
DATABASE_URL
UPLOAD_DIR
MAX_UPLOAD_MB
```

Si `DATABASE_URL` esta vacia, la aplicacion usa SQLite en `PRUNIN_DB` o `prunin.db`.
Para PostgreSQL:

```powershell
$env:DATABASE_URL="postgresql://prunin:prunin@localhost:5432/prunin"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Mas detalle en `docs/operacion/configuracion_postgresql.md`.

## Pruebas

```powershell
$env:Path='C:\Program Files\nodejs;' + $env:Path
cd frontend
npm run typecheck
npm run build
cd ..
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado actual esperado:

```text
86 passed
```

## Contratos API

Regenerar OpenAPI y tipos TypeScript:

```powershell
.\.venv\Scripts\python.exe scripts\generate_api_contracts.py
```

## Notas

- `GET /` sirve el build React desde `frontend/dist`.
- `/api/*` expone FastAPI.
- `static/i18n/*.json` se mantiene como catalogo multidioma.
- `uploads/` y `prunin.db` se generan localmente y no deben versionarse.
