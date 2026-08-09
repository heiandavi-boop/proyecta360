# Observabilidad Operativa

## Endpoints

- `GET /api/health`: liveness publico.
- `GET /api/health/ready`: readiness publico con verificacion de base de datos.
- `GET /api/ops/metrics`: metricas operativas protegidas para `Administrador`.

## Auditoria

Cada mutacion protegida bajo `/api/*` registra un evento en `audit_events` con usuario, rol, metodo, ruta, estado HTTP, host cliente y fecha.

## Pendientes de produccion

- Exportar logs estructurados a un colector externo.
- Agregar correlacion por request id.
- Definir alertas sobre errores 5xx, crecimiento de auditoria, fallos de readiness y latencia.
