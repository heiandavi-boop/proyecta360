# Final React Migration

The main application route now prioritizes the React build in `frontend/dist`.

## Completed Frontend Coverage

- Portfolio: open and create projects.
- Master Plan: create, update, delete, indent and outdent tasks.
- Scrum: create user stories.
- Risks: create risks.
- Resources: create resources.
- Conversations: create threads and messages.
- Knowledge: create components, create deliverables and upload evidence files.
- Project AI: run internal analysis and approve, reject or apply recommendations.

## Runtime Model

- `GET /` serves `frontend/dist/index.html` when the React build exists.
- `/assets/*` serves Vite build assets.
- Static legacy UI files were removed. `GET /` expects the React build to exist.

## Commands

Build React:

```powershell
cd frontend
npm run build
```

Run the integrated server:

```powershell
cd ..
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

After building, open:

```text
http://127.0.0.1:8000
```
