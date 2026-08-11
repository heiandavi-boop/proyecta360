# Backlog Operativo PRUNIN

## Fase 1 - Persistencia y configuracion productiva

Estado: implementada en este ciclo.

- Soportar `DATABASE_URL` para PostgreSQL y conservar SQLite como modo local.
- Centralizar variables `APP_ENV`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `UPLOAD_DIR` y `MAX_UPLOAD_MB`.
- Publicar `.env.example`.
- Evitar SQL exclusivo de SQLite en bootstrap de esquema mediante DDL PostgreSQL inicial.
- Documentar decision de migraciones: Alembic queda diferido hasta adoptar ORM o migraciones SQL versionadas.
- Probar SQLite por defecto, aceptacion de `DATABASE_URL`, creacion de esquema y endpoints existentes.

## Fase 2 - Seguridad y control de acceso real

Estado: base operativa implementada.

- Sustituir autenticacion demo por gestion robusta de usuarios, sesiones y secretos.
- Revisar permisos por rol en cada endpoint critico.
- Endurecer carga/descarga de evidencias.
- Agregar auditoria para acciones sensibles.

Implementado: politicas admin-only para `/api/seed`, `/api/ai/settings` y `/api/ops/*`; auditoria automatica de mutaciones API; usuario publico con `organization_id`.

## Fase 3 - Modelo de datos operativo

Estado: base operativa implementada.

- Normalizar entidades de proyecto, componentes, tareas, riesgos, entregables y conversaciones.
- Definir indices, restricciones y reglas de integridad por dominio.
- Crear estrategia de migraciones versionadas.

Implementado: tabla `organizations`, columna `organization_id` en usuarios/proyectos, tabla `audit_events` e indices operativos para proyectos, tareas, dependencias, riesgos, entregables y auditoria.

## Fase 4 - Calidad de datos e importacion

Estado: base operativa implementada.

- Validaciones exhaustivas de CSV.
- Reportes de errores por fila y entidad.
- Importacion idempotente con confirmacion previa.
- Plantillas oficiales de carga.

Implementado: prevalidacion CSV por fila/campo antes de insertar datos, errores estructurados para frontend, validacion de fechas, avances, duracion, dependencias, riesgo y duplicados `import_id`.

## Fase 5 - Experiencia de usuario productiva

Estado: mejora inicial implementada.

- Flujos completos para PM, administrador y consulta.
- Estados vacios, carga, error y permisos en todas las pantallas.
- Revision responsive y accesibilidad basica.

Implementado: el cliente frontend muestra errores estructurados de API/CSV en lenguaje accionable y conserva los controles por rol existentes.

## Fase 6 - Cronograma avanzado

Estado: mejora inicial implementada.

- Calculo formal de ruta critica.
- Dependencias con lag por tipo.
- Calendarios laborales configurables.
- Deteccion de conflictos de fechas.

Implementado: KPI y marcas visuales usan cadena critica calculada como ruta mas larga con dependencias y lag, en vez de marcar todas las tareas relacionadas con dependencias.

## Fase 7 - Reportes y portafolio

Estado: funcionalidad base existente reforzada.

- Reportes ejecutivos exportables.
- Indicadores de avance, presupuesto, riesgo y salud.
- Vistas comparativas de portafolio.

Implementado/existente: export JSON/CSV/HTML, portafolio ejecutivo, KPIs de salud y ruta critica recalculada.

## Fase 8 - IA operacional gobernada

Estado: funcionalidad base existente reforzada.

- Trazabilidad de recomendaciones.
- Politicas de aprobacion antes de aplicar cambios.
- Evaluacion de calidad de salida y explicabilidad.

Implementado/existente: recomendaciones requieren aprobacion antes de aplicarse, historial de recomendacion, undo y registro en historial del proyecto.

## Fase 9 - Observabilidad y operacion

Estado: base operativa implementada.

- Logs estructurados.
- Health checks.
- Metricas tecnicas y funcionales.
- Runbooks de respaldo, restauracion y despliegue.

Implementado: `/api/health/ready` con verificacion de base de datos y `/api/ops/metrics` con contadores y auditoria reciente para administradores.

## Fase 10 - Preparacion SaaS

Estado: base inicial implementada.

- Multi-tenant.
- Aislamiento de datos por organizacion.
- Facturacion e integraciones.
- Politicas de retencion y cumplimiento.

Implementado: tabla de organizaciones y claves `organization_id` como base de evolucion multi-tenant. Aislamiento estricto por tenant queda pendiente como siguiente incremento antes de SaaS real.
