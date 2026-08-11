from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi import APIRouter


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".csv", ".xlsx", ".docx", ".pptx"}
BLOCKED_EXTENSIONS = {".html", ".htm", ".svg", ".js", ".mjs", ".exe", ".bat", ".cmd", ".ps1", ".sh", ".php"}
ALLOWED_ENTITY_TYPES = {"Proyecto", "Tarea", "Entregable", "Riesgo", "Componente"}


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    add_history = ctx.add_history
    db = ctx.db
    get_project_or_404 = ctx.get_project_or_404
    init_db = ctx.init_db
    MAX_UPLOAD_BYTES = ctx.MAX_UPLOAD_BYTES
    one = ctx.one
    public_user = ctx.public_user
    safe_filename = ctx.safe_filename
    serialize_evidence = ctx.serialize_evidence
    UPLOAD_DIR = ctx.UPLOAD_DIR
    user_from_authorization = ctx.user_from_authorization
    assert_task_in_project = ctx.assert_task_in_project
    def secure_upload_path(path_value: str) -> Path:
        base = UPLOAD_DIR.resolve()
        path = Path(path_value).resolve()
        if base != path and base not in path.parents:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        return path

    @router.post("/api/evidences/upload")
    async def upload_evidence(
        project_id: int = Form(...),
        entity_type: str = Form("Proyecto"),
        entity_id: Optional[int] = Form(default=None),
        uploaded_by: str = Form("Sistema"),
        description: str = Form(""),
        file: UploadFile = File(...),
        authorization: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            get_project_or_404(conn, project_id)
            user = user_from_authorization(conn, authorization)
            actor = public_user(user)["name"] if user else uploaded_by
            if entity_type not in ALLOWED_ENTITY_TYPES:
                raise HTTPException(status_code=400, detail="Tipo de entidad de evidencia inválido")
            if entity_type == "Tarea" and entity_id:
                assert_task_in_project(conn, entity_id, project_id)
            if entity_type == "Entregable" and entity_id:
                deliverable = one(conn, "SELECT id FROM deliverables WHERE id = ? AND project_id = ?", (entity_id, project_id))
                if not deliverable:
                    raise HTTPException(status_code=400, detail="Entregable inválido para este proyecto")
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="El archivo supera el tama\u00f1o m\u00e1ximo permitido")
        original = safe_filename(file.filename or "evidencia.bin")
        suffix = Path(original).suffix
        if suffix.lower() in BLOCKED_EXTENSIONS or suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")
        stored = f"{project_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(6)}{suffix}"
        project_dir = UPLOAD_DIR / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        target = project_dir / stored
        target.write_bytes(raw)
        with db() as conn:
            cur = conn.execute(
                """INSERT INTO evidence_files (project_id, entity_type, entity_id, original_filename, stored_filename, content_type, size_bytes, uploaded_by, description, file_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_id, entity_type, entity_id, original, stored, "application/octet-stream", len(raw), actor, description, str(target)),
            )
            url = f"/api/evidences/{cur.lastrowid}/download"
            if entity_type == "Entregable" and entity_id:
                conn.execute("UPDATE deliverables SET evidence_url = ? WHERE id = ? AND project_id = ?", (url, entity_id, project_id))
            add_history(conn, project_id, "Evidencia", original, "Cargada", f"Asociada a {entity_type} {entity_id or ''}", actor)
            conn.commit()
            return serialize_evidence(one(conn, "SELECT * FROM evidence_files WHERE id = ?", (cur.lastrowid,)))
    
    
    @router.get("/api/evidences/{evidence_id}/download")
    def download_evidence(evidence_id: int) -> FileResponse:
        init_db()
        with db() as conn:
            row = one(conn, "SELECT * FROM evidence_files WHERE id = ?", (evidence_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Evidencia no encontrada")
        path = secure_upload_path(row["file_path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail="Archivo f\u00edsico no encontrado")
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=row["original_filename"],
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename(row["original_filename"])}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router


