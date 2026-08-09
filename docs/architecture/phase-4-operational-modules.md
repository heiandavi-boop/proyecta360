# Phase 4 - Operational React Modules

Phase 4 starts moving real user workflows into the parallel React frontend while keeping the existing static UI available.

## Scope

- Portfolio can create a project through `POST /api/projects`.
- Portfolio can open a project and refresh bootstrap data.
- Master Plan can create a task through `POST /api/tasks`.
- React calls use generated API contract names from `contracts/api`.
- New labels are routed through the existing i18n catalogs.

## Not In This Cut

- Full task editing, delete, indent/outdent, dependencies and CSV import remain in the legacy UI until later phases.
- React is still served as a parallel frontend; the existing static UI is not removed.

## Validation

Run:

```powershell
$env:Path='C:\Program Files\nodejs;' + $env:Path
npm run typecheck
npm run build
.\.venv\Scripts\python.exe -m pytest -q
```
