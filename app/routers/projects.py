import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.db import deep_merge, dumps, get_db, iso_value, loads
from app.schemas import PROJECT_UPDATE_COLUMNS, ProjectIn, ProjectUpdate
from app.services.graph import get_project_or_404
from app.services.metrics import calculate_metrics
from app.services.serializers import serialize_project
from core.defaults import DEFAULT_PARAMETERS

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("")
def create_project(payload: ProjectIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    parameters = deep_merge(DEFAULT_PARAMETERS, payload.parameters)
    cur = conn.execute(
        """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, methodology, status, budget, currency, parameters_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (payload.name, payload.description, payload.sponsor, payload.project_manager, iso_value(payload.start_date), iso_value(payload.end_date), payload.methodology, payload.status, payload.budget, payload.currency, dumps(parameters)),
    )
    conn.commit()
    return serialize_project(get_project_or_404(conn, cur.lastrowid))


@router.put("/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    current = get_project_or_404(conn, project_id)
    data = payload.model_dump(exclude_unset=True)
    start_date = iso_value(data.get("start_date", current["start_date"]))
    end_date = iso_value(data.get("end_date", current["end_date"]))
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="La fecha fin no puede ser menor a la fecha inicio")
    if "parameters" in data and data["parameters"] is not None:
        existing_parameters = loads(current["parameters_json"], DEFAULT_PARAMETERS)
        data["parameters_json"] = dumps(deep_merge(existing_parameters, data.pop("parameters")))
    fields = []
    args = []
    for k, v in data.items():
        if k not in PROJECT_UPDATE_COLUMNS:
            raise HTTPException(status_code=400, detail=f"Campo no actualizable: {k}")
        fields.append(f"{k} = ?")
        args.append(iso_value(v))
    if fields:
        args.append(project_id)
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", tuple(args))
        conn.commit()
    return serialize_project(get_project_or_404(conn, project_id))


@router.get("/{project_id}/metrics")
def metrics(project_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    return calculate_metrics(conn, project_id)
