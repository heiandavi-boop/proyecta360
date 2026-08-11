# Configuracion PostgreSQL

Fase 1 habilita PostgreSQL mediante `DATABASE_URL` sin retirar SQLite del modo local.

## Variables

- `DATABASE_URL`: si esta vacia, PRUNIN usa SQLite en `PRUNIN_DB`.
- `APP_ENV`: ambiente logico (`local`, `staging`, `production`).
- `SECRET_KEY`: clave de aplicacion. Cambiar siempre fuera de local.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: minutos de vigencia del token de sesion.
- `UPLOAD_DIR`: carpeta de evidencias.
- `MAX_UPLOAD_MB`: tamano maximo de archivo en MB.

## Ejecucion local con SQLite

```powershell
cd "C:\Users\atruj\OneDrive\Escritorio\Proyecto alejandra\proyecta360_mvp_v21_msproject\proyecta360_ai_project"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

## Ejecucion con PostgreSQL

```powershell
$env:DATABASE_URL="postgresql://prunin:prunin@localhost:5432/prunin"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Al iniciar, `init_db()` crea el esquema si no existe y aplica columnas faltantes basicas. La aplicacion conserva placeholders SQLite en sus rutas y los traduce en la capa de conexion para PostgreSQL.

## Migraciones

El codigo actual usa SQL manual y no SQLAlchemy, por lo que Alembic no aplica limpiamente sin introducir una reescritura de persistencia mayor. Para esta fase se deja una migracion inicial operativa mediante el bootstrap de esquema (`create_schema` + `ensure_schema_columns`) compatible con SQLite/PostgreSQL. La adopcion formal de Alembic queda en backlog cuando se migre a SQLAlchemy o se defina una estrategia de migraciones SQL versionadas.
