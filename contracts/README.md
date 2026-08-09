# Proyecta360 API Contracts

Esta carpeta es la base de la fase 1 de migracion hacia un frontend React + TypeScript.

## Fuente de verdad

FastAPI genera el contrato OpenAPI desde los schemas Pydantic y los endpoints registrados.

Archivos generados:

- `api/openapi.json`: snapshot versionado del contrato HTTP.
- `api/types.ts`: tipos TypeScript derivados de schemas y operaciones.
- `api/endpoints.ts`: mapa tipado de endpoints disponibles.

## Regenerar contratos

```powershell
.\.venv\Scripts\python.exe scripts\generate_api_contracts.py
```

## Regla de arquitectura

El frontend nuevo debe consumir estos contratos en vez de inventar formas de datos en componentes.
Cuando cambie una respuesta o request del backend, se regeneran los contratos y se corrigen los tipos del frontend.
