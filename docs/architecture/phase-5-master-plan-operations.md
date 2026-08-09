# Phase 5 - Master Plan Operations

Phase 5 expands the React Master Plan from creation-only to basic task management.

## Scope

- Update task status through `PUT /api/tasks/{task_id}`.
- Update task progress through `PUT /api/tasks/{task_id}`.
- Delete tasks through `DELETE /api/tasks/{task_id}`.
- Apply and remove task indentation through the existing outline endpoints.
- Refresh project bootstrap data after each mutation so KPIs and schedule views stay consistent.

## Remaining Work

- Full task edit modal.
- Dependency editing.
- Bulk schedule operations.
- Rich Gantt canvas/timeline interaction.

## Validation

Run:

```powershell
$env:Path='C:\Program Files\nodejs;' + $env:Path
npm run typecheck
npm run build
.\.venv\Scripts\python.exe -m pytest -q
```
