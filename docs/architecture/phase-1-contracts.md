# Fase 1 - Contratos Para Migracion Frontend

## Objetivo

Preparar la migracion a React + TypeScript sin reemplazar todavia la interfaz actual.

## Decision

La fuente de verdad de contratos sera OpenAPI generado por FastAPI.
Desde ese contrato se generan tipos TypeScript estables para el futuro frontend.

## Entregables

- Contrato OpenAPI versionado en `contracts/api/openapi.json`.
- Tipos TypeScript en `contracts/api/types.ts`.
- Mapa de endpoints en `contracts/api/endpoints.ts`.
- Script reproducible en `scripts/generate_api_contracts.py`.

## Uso En Fases Siguientes

La fase 2 debe crear `frontend/` con Vite + React + TypeScript y consumir estos archivos.
La fase 3 debe empezar a reemplazar vistas usando tipos de `contracts/api/types.ts`.

## No Cambia

- Nota historica: en fase 1 la app estatica seguia activa. Tras la migracion final, la UI principal es React y los archivos legacy fueron retirados.
- Los endpoints existentes se mantienen.
- La carpeta externa `proyecta360_training_standalone_v5` no forma parte de esta migracion.
