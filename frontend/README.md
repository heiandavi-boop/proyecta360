# Proyecta360 Frontend

Frontend principal de Proyecta360 en React + TypeScript.

## Requisitos

- Node.js LTS
- Backend FastAPI corriendo en `http://127.0.0.1:8000`

## Ejecutar

```powershell
cd frontend
npm install
npm run dev
```

Abrir:

```text
http://127.0.0.1:5173
```

## Arquitectura

- `src/api`: cliente HTTP tipado contra FastAPI.
- `src/domain`: tipos refinados para la UI.
- `src/i18n`: estado y carga de idiomas desde `/api/i18n`.
- `src/components`: piezas visuales reutilizables.
- `src/features`: pantallas por dominio.

El build de produccion se sirve desde FastAPI cuando existe `frontend/dist`.
