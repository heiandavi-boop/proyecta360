# Fase 3 - Base Visual y Navegacion React

## Objetivo

Convertir el frontend React paralelo en una base navegable por dominios, lista para migrar funcionalidades reales modulo por modulo.

## Alcance Implementado

- Navegacion principal con estado `AppView`.
- Selector real de proyecto que recarga `/api/bootstrap?project_id=...`.
- `ProjectShell` compartido para encabezado, selector y contenido.
- Vistas base por dominio:
  - Portafolio
  - Plan Maestro
  - Scrum
  - Recursos
  - Riesgos
  - Conversaciones
  - Conocimiento
  - IA del Proyecto
- Estilos responsive para tablas, tarjetas, tableros y paneles.

## Regla de Migracion

Cada fase posterior debe reemplazar una vista base por una vista funcional completa sin tocar el shell general.

## Validacion Pendiente Con Node

Cuando `node` y `npm` esten disponibles:

```powershell
cd frontend
npm install
npm run typecheck
npm run build
```
