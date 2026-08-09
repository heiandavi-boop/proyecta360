# Phase 6 - Domain Create Flows

Phase 6 connects additional React modules to real backend mutations.

## Scope

- Scrum can create user stories through `POST /api/stories`.
- Risks can create risks through `POST /api/risks`.
- Resources can create resources through `POST /api/resources`.
- All new form labels use the shared i18n catalogs.
- Bootstrap data is refreshed after each create operation.

## Remaining Work

- Edit and delete flows for stories, risks and resources.
- Sprint creation and story assignment.
- Risk response workflow and mitigation follow-up alerts in the React UI.
- Resource allocation by task or component.

## Validation

Run:

```powershell
$env:Path='C:\Program Files\nodejs;' + $env:Path
npm run typecheck
npm run build
.\.venv\Scripts\python.exe -m pytest -q
```
