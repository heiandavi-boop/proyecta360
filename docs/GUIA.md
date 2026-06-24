# Guía de ejecución — Proyecta360

Cómo levantar el proyecto y trabajar con las migraciones de base de datos.

> Todos los comandos se ejecutan desde la raíz del proyecto
> (`/Users/cloudnonic/Desktop/proyecta360`) y usando el entorno virtual `.venv`.

---

## 1. Setup inicial (una sola vez)

```bash
# 1. Crear el entorno virtual
python3 -m venv .venv

# 2. Instalar dependencias
.venv/bin/python -m pip install -r requirements.txt

# 3. (Opcional) configurar variables de entorno
cp .env.example .env        # ajusta valores si lo necesitas
```

No hace falta crear la base de datos a mano: se crea sola al primer arranque.

---

## 2. Correr la aplicación

```bash
.venv/bin/python -m uvicorn app:app --reload
```

Luego abrir en el navegador: **http://127.0.0.1:8000**

Qué pasa al arrancar (automático, en este orden):
1. **Se aplican las migraciones pendientes** (`alembic upgrade head`) — la BD queda al día sola.
2. **Se siembran los datos demo** (proyecto "Plataforma Cliente 360") si la BD está vacía.

> El `--reload` reinicia el servidor al guardar cambios. Quítalo en producción.

---

## 3. Migraciones de base de datos (Alembic)

La estructura de la BD la gestiona **Alembic**. Cada cambio de esquema (añadir
columna, tabla, índice…) es un script versionado en [`alembic/versions/`](../alembic/versions/).

### Correr migraciones

En el día a día **no hace falta correrlas a mano**: la app las aplica al arrancar.
Para hacerlo manualmente:

```bash
.venv/bin/alembic current        # ¿en qué versión está la BD?
.venv/bin/alembic history        # ver la cadena de migraciones
.venv/bin/alembic upgrade head   # aplicar todas las pendientes
.venv/bin/alembic upgrade +1     # aplicar solo la siguiente
.venv/bin/alembic downgrade -1   # revertir la última
```

Alembic toma la conexión a la BD desde [`core/config.py`](../core/config.py)
(vía `alembic/env.py`), así que respeta tu `.env`. No hay que pasarle la URL.

### Crear una migración nueva

```bash
.venv/bin/alembic revision -m "descripcion corta del cambio"
```

Esto genera un archivo nuevo en `alembic/versions/` con el esqueleto listo
(`revision`, `down_revision` apuntando al head actual, y `upgrade()`/`downgrade()`
vacíos). Luego **escribes el cambio a mano** dentro de las funciones:

```python
def upgrade():
    op.execute("ALTER TABLE tasks ADD COLUMN tags TEXT DEFAULT ''")

def downgrade():
    op.execute("ALTER TABLE tasks DROP COLUMN tags")
```

Aplícala con `.venv/bin/alembic upgrade head` (o reiniciando la app).

#### ⚠️ Dos cosas importantes en este proyecto

1. **No hay modelos SQLAlchemy** (`target_metadata = None`), por lo que
   `--autogenerate` **NO funciona aquí**. Las migraciones se escriben a mano con
   `op.execute(...)` (SQL crudo).
2. En **SQLite**, recrear una tabla (cambiar/quitar columnas o constraints) con
   `op.batch_alter_table` **pierde el `ON DELETE CASCADE`** de las claves foráneas.
   Para recrear una tabla, usa **recreación explícita** (crear tabla nueva →
   copiar datos → `DROP` → `RENAME`), como en
   [`0002_drop_risks_level.py`](../alembic/versions/0002_drop_risks_level.py).

#### Estilo de nombres (opcional)

`alembic revision` genera un id aleatorio (hash). Si quieres mantener el estilo
numerado (`0003_mi_cambio`), pásalo explícito:

```bash
.venv/bin/alembic revision --rev-id 0003_mi_cambio -m "mi cambio"
```

### Migraciones actuales

```
<base> -> 0001_baseline          # esquema inicial (7 tablas + índices)
0001_baseline -> 0002_drop_risks_level   # elimina risks.level (ahora derivado en lectura)
```

---

## 4. Variables de entorno

Se configuran en `.env` (ver [`.env.example`](../.env.example)). Todas son opcionales.

| Variable | Default | Para qué |
|---|---|---|
| `PROYECTA360_DB` | `<proyecto>/proyecta360.db` | Ruta del archivo SQLite |
| `PROYECTA360_CORS_ORIGINS` | `http://127.0.0.1:8000,http://localhost:8000` | Orígenes CORS permitidos |
| `PROYECTA360_ENV` | `local` | Entorno (local / staging / production) |
| `PROYECTA360_LOG_LEVEL` | `INFO` | Nivel de log |
| `PROYECTA360_SEED_ON_STARTUP` | `true` | Cargar datos demo si la BD está vacía |

---

## 5. Tests

```bash
.venv/bin/python -m pytest -q
```

Cada test corre contra una base de datos temporal aislada (no toca tu BD local).

---

## 6. Mapa rápido del proyecto

```
app/         Backend FastAPI (paquete segmentado)
  db.py        conexión, get_db, run_migrations, helpers
  schemas.py   modelos Pydantic
  services/    serializers, metrics, graph, bootstrap, ai
  routers/     un APIRouter por dominio
  main.py      create_app() — punto de entrada
core/        configuración compartida (config.py, defaults.py)
alembic/     migraciones (versions/) + env.py
static/      Frontend SPA en ES modules (js/ + js/views/)
```

### Comandos de referencia rápida

```bash
.venv/bin/python -m uvicorn app:app --reload   # correr la app
.venv/bin/alembic upgrade head                 # aplicar migraciones
.venv/bin/alembic revision -m "..."            # crear una migración
.venv/bin/python -m pytest -q                  # correr tests
```
