# Fase 2 - Frontend React Paralelo

## Objetivo

Crear una aplicacion React + TypeScript paralela sin sustituir aun la interfaz actual en `static/`.

## Alcance Implementado

- App Vite en `frontend/`.
- Cliente API tipado que consume `contracts/api/endpoints.ts` y `contracts/api/types.ts`.
- Login contra `/api/auth/login`.
- Carga inicial desde `/api/bootstrap`.
- Selector de idioma consumiendo `/api/i18n/languages` y `/api/i18n/catalog/{locale}`.
- Dashboard inicial con KPIs, portafolio y tareas principales.

## Como Ejecutar

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Terminal 2:

```powershell
cd frontend
npm install
npm run dev
```

Abrir:

```text
http://127.0.0.1:5173
```

## Nota

En esta maquina no se detecto `node` ni `npm`, por lo que la validacion ejecutada fue de backend y estructura.
Cuando Node.js LTS este instalado, ejecutar:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Siguiente Fase

La fase 3 debe migrar la base visual y navegacion principal con mas fidelidad:

- Header definitivo.
- Layout responsive.
- Rutas/vistas por dominio.
- Estado global de sesion/proyecto.
- Seleccion real de proyecto.
