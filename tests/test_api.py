import pytest
from io import BytesIO
import csv
import io
import json
from pathlib import Path
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from proyecta360 import main as main_module
from proyecta360.services.internal_ai_engine import analyze_project_internal_ai


@pytest.fixture
def client(tmp_path):
    main_module.DB_PATH = tmp_path / "prunin_test.db"
    with TestClient(app_module.app) as c:
        yield c


def auth_headers(client, email="admin@prunin.local", password="admin123"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def project_required_context(**overrides):
    payload = {
        "project_manager": "PMO",
        "sponsor": "Sponsor",
        "contractual_end_date": "2026-12-31",
        "budget": 1000,
        "currency": "COP",
        "problem_statement": "Brecha estrategica que justifica el proyecto",
        "general_objective": "Cerrar la brecha con resultados medibles",
    }
    payload.update(overrides)
    return payload



def test_bootstrap_requires_session(client):
    response = client.get("/api/bootstrap")

    assert response.status_code == 401

def test_bootstrap_seeds_default_project(client):
    response = client.get("/api/bootstrap", headers=auth_headers(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload["projects"]
    assert payload["current_project"]["name"] == "PRUNIN LAC"
    assert payload["components"]
    assert payload["deliverables"]
    assert payload["history"]
    assert payload["conversation_threads"]
    assert payload["conversation_messages"]
    assert payload["intelligence"]["recommendations"]
    strategic = payload["current_project"]["parameters"]["strategic_framework"]
    assert "plataforma de inteligencia contextual" in strategic["general_objective"]
    assert strategic["objective_indicators"]


def test_project_strategic_framework_can_be_updated(client):
    headers = auth_headers(client)
    payload = client.get("/api/bootstrap", headers=headers).json()
    project_id = payload["current_project"]["id"]
    response = client.put(
        f"/api/projects/{project_id}",
        headers=headers,
        json={"parameters": {"strategic_framework": {"problem_statement": "Nueva brecha estrategica validada"}}},
    )

    assert response.status_code == 200
    strategic = response.json()["parameters"]["strategic_framework"]
    assert strategic["problem_statement"] == "Nueva brecha estrategica validada"
    assert strategic["general_objective"]


def test_create_project_captures_context_for_ai(client):
    response = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json=project_required_context(
            name="Proyecto contextual",
            project_code="CTX-001",
            description="Proyecto con contexto completo",
            requesting_area="Direccion de innovacion",
            project_type="Transformacion",
            methodology="Scrum",
            priority="Alta",
            start_date="2026-09-01",
            contractual_end_date="2026-12-20",
            problem_statement="La entidad no tiene trazabilidad de indicadores territoriales",
            current_situation="Los indicadores se consolidan manualmente",
            consequence_if_not_done="Se perdera oportunidad de decision temprana",
            general_objective="Implementar seguimiento contextual de indicadores",
            specific_objectives="1. Integrar fuentes\n2. Publicar tablero",
            objective_indicators="Indicador 1: cobertura semanal",
            scope_included="Tablero, carga y auditoria",
            scope_excluded="ERP financiero",
            success_criteria="Indicadores publicados y auditables",
            project_context="Proyecto para equipos regionales",
            stakeholders="PMO, direcciones regionales y sponsor",
            external_dependencies="Disponibilidad de datos fuente",
            regulatory_constraints="Politica de datos institucional",
            responsible_team="Equipo analitica",
        ),
    )

    assert response.status_code == 200
    project = response.json()
    assert project["project_code"] == "CTX-001"
    assert project["problem_statement"].startswith("La entidad")
    assert project["ai_context"]["general_objective"] == "Implementar seguimiento contextual de indicadores"
    assert project["ai_context"]["stakeholders"] == "PMO, direcciones regionales y sponsor"


def test_create_project_allows_context_fields_to_be_completed_later(client):
    response = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json={
            "name": "Proyecto incompleto",
            "project_manager": "PM",
            "sponsor": "Sponsor",
            "start_date": "2026-09-01",
            "contractual_end_date": "2026-12-31",
            "budget": 1000,
            "currency": "COP",
        },
    )

    assert response.status_code == 200
    project = response.json()
    assert project["name"] == "Proyecto incompleto"
    assert project["problem_statement"] == ""
    assert project["general_objective"] == ""


def test_create_project_allows_missing_contractual_end_date(client):
    response = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json={
            "name": "Proyecto sin compromiso",
            "project_manager": "PM",
            "sponsor": "Sponsor",
            "start_date": "2026-09-01",
            "budget": 0,
            "currency": "COP",
        },
    )

    assert response.status_code == 200
    project = response.json()
    assert project["name"] == "Proyecto sin compromiso"
    assert project["contractual_end_date"] in (None, "")
    assert project["budget"] == 0


def test_create_task_allows_missing_start_date(client):
    headers = auth_headers(client)
    boot = client.get("/api/bootstrap", headers=headers).json()
    project_id = boot["current_project"]["id"]
    project_start = boot["current_project"]["start_date"]
    response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Tarea sin fecha de inicio",
            "end_date": "2026-09-10",
            "progress": 0,
        },
    )

    assert response.status_code == 200
    task = response.json()
    assert task["project_id"] == project_id
    assert task["start_date"] == project_start
    assert task["end_date"] == "2026-09-10"
    assert task["owner"] == ""


def test_create_task_defaults_to_project_start_and_respects_duration(client):
    headers = auth_headers(client)
    boot = client.get("/api/bootstrap", headers=headers).json()
    project_id = boot["current_project"]["id"]
    project_start = boot["current_project"]["start_date"]
    # Create a task without start_date but with duration_days = 5
    response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Tarea sin fecha pero con duracion",
            "duration_days": 5,
        },
    )

    assert response.status_code == 200
    task = response.json()
    assert task["project_id"] == project_id
    assert task["start_date"] == project_start
    assert int(task.get("duration_days", 0)) == 5
    # end_date should be project_start + 4 days
    from datetime import datetime, timedelta

    expected_end = (datetime.fromisoformat(project_start) + timedelta(days=4)).date().isoformat()
    assert task["end_date"] == expected_end


def test_update_project_context_fields(client):
    headers = auth_headers(client)
    created = client.post(
        "/api/projects",
        headers=headers,
        json=project_required_context(name="Proyecto editable", start_date="2026-09-01"),
    ).json()

    response = client.put(
        f"/api/projects/{created['id']}",
        headers=headers,
        json={
            "problem_statement": "Brecha actualizada para analisis IA",
            "general_objective": "Objetivo actualizado",
            "scope_included": "Incluye piloto regional",
            "stakeholders": "Sponsor, PMO y usuarios clave",
        },
    )

    assert response.status_code == 200
    project = response.json()
    assert project["problem_statement"] == "Brecha actualizada para analisis IA"
    assert project["scope_included"] == "Incluye piloto regional"
    assert project["ai_context"]["stakeholders"] == "Sponsor, PMO y usuarios clave"


def test_import_project_from_csv_creates_related_records(client):
    headers = auth_headers(client)
    csv_data = "\n".join([
        "entity,import_id,name,title,description,start_date,end_date,duration_days,project_manager,budget,currency,component_ref,predecessor_ref,successor_ref,probability,impact,response,owner,due_date,problem_statement,general_objective",
        "project,,Proyecto CSV,,,2026-09-01,2026-09-30,,PM CSV,1000,COP,,,,,,,,,Brecha CSV,Objetivo CSV",
        "component,C1,Componente CSV,,,,,,,,,,,,,,,,,,",
        "resource,,Ana CSV,,,,,,,,,,,,,,,,Lider,,",
        "task,T1,,Tarea 1,,2026-09-01,,1,,,,C1,,,,,,Ana CSV,,,",
        "task,T2,,Tarea 2,,2026-09-02,,2,,,,C1,,,,,,Ana CSV,,,",
        "dependency,,,,,,,,,,,,T1,T2,,,,,,,",
        "risk,,Riesgo CSV,,,,,,,,,,,,4,4,Mitigar,PM CSV,,,",
        "deliverable,,Entregable CSV,,,,,,,,,C1,,,,,,PM CSV,2026-09-20,,",
    ])
    response = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("proyecto.csv", BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["name"] == "Proyecto CSV"
    assert body["project"]["parameters"]["strategic_framework"]["general_objective"] == "Objetivo CSV"
    assert body["counts"]["tasks"] == 2
    assert body["counts"]["dependencies"] == 1
    payload = client.get(f"/api/bootstrap?project_id={body['project_id']}", headers=headers).json()
    assert len(payload["tasks"]) == 2
    assert len(payload["dependencies"]) == 1
    assert payload["risks"][0]["title"] == "Riesgo CSV"


def test_import_project_from_csv_accepts_context_columns(client):
    headers = auth_headers(client)
    csv_data = "\n".join([
        "entity,import_id,name,description,start_date,end_date,contractual_end_date,project_manager,sponsor,budget,currency,project_code,requesting_area,project_type,priority,problem_statement,general_objective,objective_indicators,scope_included,scope_excluded,project_context,stakeholders,external_dependencies,regulatory_constraints",
        "project,,Proyecto Contexto CSV,Contextual,2026-09-01,2026-09-30,2026-10-15,PM CSV,Sponsor CSV,1000,COP,CSV-CTX,Cliente interno,Innovacion,Alta,Brecha CSV contextual,Objetivo CSV contextual,Indicador CSV,Incluido CSV,Excluido CSV,Contexto territorial CSV,Stakeholders CSV,Dependencia CSV,Regla CSV",
    ])

    response = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("contexto.csv", BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["project_code"] == "CSV-CTX"
    assert project["ai_context"]["problem_statement"] == "Brecha CSV contextual"
    assert project["ai_context"]["external_dependencies"] == "Dependencia CSV"


def test_import_project_csv_returns_row_level_validation_errors(client):
    headers = auth_headers(client)
    csv_data = "\n".join([
        "entity,import_id,name,title,start_date,end_date,duration_days,progress,predecessor_ref,successor_ref,probability,impact",
        "project,,Proyecto invalido,,2026-09-30,2026-09-01,,,,,,",
        "task,T1,,Tarea mala,fecha-mala,,0,120,,,,",
        "dependency,,,,,,,,T1,,,,",
        "risk,,Riesgo malo,,,,,,,,9,0",
    ])

    response = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("errores.csv", BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["message"] == "El CSV contiene errores de validacion"
    assert any(error["row"] == 2 and error["field"] == "end_date" for error in detail["errors"])
    assert any(error["row"] == 3 and error["field"] == "progress" for error in detail["errors"])
    assert any(error["row"] == 4 and error["field"] == "successor_ref" for error in detail["errors"])


def test_rejects_invalid_task_progress(client):
    project_id = client.get("/api/bootstrap", headers=auth_headers(client)).json()["current_project"]["id"]
    response = client.post(
        "/api/tasks",
        headers=auth_headers(client),
        json={
            "project_id": project_id,
            "title": "Actividad inválida",
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
            "progress": 120,
        },
    )

    assert response.status_code == 422


def test_rejects_cross_project_dependency(client):
    first = client.get("/api/bootstrap", headers=auth_headers(client)).json()
    first_project_id = first["current_project"]["id"]
    first_task_id = first["tasks"][0]["id"]
    second_project_id = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json=project_required_context(
            name="Proyecto B",
            start_date="2026-07-01",
            end_date="2026-08-01",
        ),
    ).json()["id"]
    second_task_id = client.post(
        "/api/tasks",
        headers=auth_headers(client),
        json={
            "project_id": second_project_id,
            "title": "Tarea B",
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
        },
    ).json()["id"]
    response = client.post(
        "/api/dependencies",
        headers=auth_headers(client),
        json={
            "project_id": first_project_id,
            "predecessor_id": first_task_id,
            "successor_id": second_task_id,
        },
    )

    assert response.status_code == 400


def test_rejects_dependency_cycle(client):
    payload = client.get("/api/bootstrap", headers=auth_headers(client)).json()
    project_id = payload["current_project"]["id"]
    first_task_id = payload["tasks"][0]["id"]
    new_task_id = client.post(
        "/api/tasks",
        headers=auth_headers(client),
        json={
            "project_id": project_id,
            "title": "Nueva tarea",
            "start_date": "2026-07-05",
            "end_date": "2026-07-06",
            "predecessor_id": first_task_id,
        },
    ).json()["id"]
    response = client.post(
        "/api/dependencies",
        headers=auth_headers(client),
        json={
            "project_id": project_id,
            "predecessor_id": new_task_id,
            "successor_id": first_task_id,
        },
    )

    assert response.status_code == 400


def test_task_toggle_collapses_and_expands(client):
    payload = client.get("/api/bootstrap", headers=auth_headers(client)).json()
    task_id = payload["tasks"][0]["id"]

    collapsed = client.post(f"/api/tasks/{task_id}/toggle", headers=auth_headers(client))
    expanded = client.post(f"/api/tasks/{task_id}/toggle", headers=auth_headers(client))

    assert collapsed.status_code == 200
    assert collapsed.json()["is_expanded"] == 0
    assert expanded.status_code == 200
    assert expanded.json()["is_expanded"] == 1


def test_rejects_cross_project_deliverable_component(client):
    first = client.get("/api/bootstrap", headers=auth_headers(client)).json()
    first_component_id = first["components"][0]["id"]
    second_project_id = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json=project_required_context(
            name="Proyecto financiado B",
            start_date="2026-07-01",
            end_date="2026-08-01",
        ),
    ).json()["id"]
    response = client.post(
        "/api/deliverables",
        headers=auth_headers(client),
        json={
            "project_id": second_project_id,
            "component_id": first_component_id,
            "name": "Producto externo",
        },
    )

    assert response.status_code == 400


def test_rejects_cross_project_conversation_message(client):
    first = client.get("/api/bootstrap", headers=auth_headers(client)).json()
    first_thread_id = first["conversation_threads"][0]["id"]
    second_project_id = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json=project_required_context(
            name="Proyecto colaborativo B",
            start_date="2026-07-01",
            end_date="2026-08-01",
        ),
    ).json()["id"]
    response = client.post(
        f"/api/conversations/{first_thread_id}/messages",
        headers=auth_headers(client),
        json={
            "thread_id": first_thread_id,
            "project_id": second_project_id,
            "author": "PMO",
            "message": "Mensaje cruzado",
        },
    )

    assert response.status_code == 400


def test_auth_login_and_me(client):
    response = client.post('/api/auth/login', json={'email':'admin@prunin.local','password':'admin123'})
    assert response.status_code == 200
    token = response.json()['token']
    me = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['user']['role'] == 'Administrador'


def test_login_hashes_token_and_migrates_password(client):
    response = client.post("/api/auth/login", json={"email": "admin@prunin.local", "password": "admin123"})
    assert response.status_code == 200
    token = response.json()["token"]

    with main_module.db() as conn:
        user = main_module.one(conn, "SELECT * FROM users WHERE email = ?", ("admin@prunin.local",))

    assert user["access_token"] == ""
    assert user["access_token_hash"]
    assert user["access_token_hash"] != token
    assert user["password_hash"].startswith("pbkdf2_sha256$")
    assert user["token_expires_at"]


def test_auth_login_accepts_browser_form_fallback(client):
    response = client.post(
        "/api/auth/login",
        data={"email": "admin@prunin.local", "password": "admin123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "Administrador"


def test_mutations_require_session(client):
    response = client.post(
        "/api/projects",
        json={"name": "Sin sesion", "start_date": "2026-09-01"},
    )

    assert response.status_code == 401


def test_consulta_role_cannot_mutate(client):
    response = client.post(
        "/api/projects",
        headers=auth_headers(client, "consulta@prunin.local", "consulta123"),
        json={"name": "No permitido", "start_date": "2026-09-01"},
    )

    assert response.status_code == 403


def test_delete_project_removes_associated_records(client):
    headers = auth_headers(client)
    create = client.post(
        "/api/projects",
        headers=headers,
        json=project_required_context(name="Proyecto para eliminar", start_date="2026-09-01", project_manager="PM"),
    )
    assert create.status_code == 200
    project_id = create.json()["id"]

    with main_module.db() as conn:
        task = conn.execute(
            "INSERT INTO tasks (project_id, title, start_date, end_date) VALUES (?, ?, ?, ?)",
            (project_id, "Tarea asociada", "2026-09-01", "2026-09-05"),
        )
        conn.execute("INSERT INTO resources (project_id, name) VALUES (?, ?)", (project_id, "Recurso asociado"))
        conn.execute("INSERT INTO budget_entries (project_id, month, planned_amount) VALUES (?, ?, ?)", (project_id, "2026-09", 100))
        conn.execute("INSERT INTO risks (project_id, title) VALUES (?, ?)", (project_id, "Riesgo asociado"))
        conn.execute("INSERT INTO sprints (project_id, name, start_date, end_date) VALUES (?, ?, ?, ?)", (project_id, "Ciclo asociado", "2026-09-01", "2026-09-15"))
        conn.execute("INSERT INTO stories (project_id, title, master_task_id) VALUES (?, ?, ?)", (project_id, "Historia asociada", task.lastrowid))
        thread = conn.execute("INSERT INTO conversation_threads (project_id, title) VALUES (?, ?)", (project_id, "Conversacion asociada"))
        conn.execute("INSERT INTO conversation_messages (thread_id, project_id, message) VALUES (?, ?, ?)", (thread.lastrowid, project_id, "Mensaje asociado"))
        conn.commit()

    response = client.delete(f"/api/projects/{project_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Proyecto eliminado"
    with main_module.db() as conn:
        assert conn.execute("SELECT COUNT(*) AS total FROM projects WHERE id = ?", (project_id,)).fetchone()["total"] == 0
        for table in ["tasks", "resources", "budget_entries", "risks", "sprints", "stories", "conversation_threads", "conversation_messages"]:
            remaining = conn.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE project_id = ?", (project_id,)).fetchone()["total"]
            assert remaining == 0, table


def test_seed_endpoint_is_admin_only(client):
    pm_response = client.post("/api/seed", headers=auth_headers(client, "alejandra@prunin.ai", "demo123"))
    admin_response = client.post("/api/seed", headers=auth_headers(client))

    assert pm_response.status_code == 403
    assert admin_response.status_code == 200


def test_mutations_are_audited_and_ops_metrics_are_admin_only(client):
    headers = auth_headers(client)
    create = client.post(
        "/api/projects",
        headers=headers,
        json=project_required_context(name="Auditado", start_date="2026-09-01", project_manager="PM"),
    )

    assert create.status_code == 200
    forbidden = client.get("/api/ops/metrics", headers=auth_headers(client, "alejandra@prunin.ai", "demo123"))
    metrics = client.get("/api/ops/metrics", headers=headers)

    assert forbidden.status_code == 403
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["counts"]["audit_events"] >= 1
    assert any(item["path"] == "/api/projects" and item["method"] == "POST" for item in body["recent_audit"])


def test_ready_health_checks_database(client):
    response = client.get("/api/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_export_json_contains_full_project(client):
    project_id = client.get('/api/bootstrap', headers=auth_headers(client)).json()['current_project']['id']
    response = client.get(f'/api/projects/{project_id}/export/json', headers=auth_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload['project']['id'] == project_id
    assert payload['components']
    assert payload['tasks']
    assert 'evidences' in payload


def test_export_csv_matches_import_structure_and_can_be_reimported(client):
    headers = auth_headers(client)
    project_id = client.get('/api/bootstrap', headers=headers).json()['current_project']['id']
    response = client.get(f'/api/projects/{project_id}/export/csv', headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0]["entity"] == "project"
    assert rows[0]["name"] == "PRUNIN LAC"
    assert any(row["entity"] == "task" and row["import_id"].startswith("T") for row in rows)
    assert any(row["entity"] == "dependency" and row["predecessor_ref"].startswith("T") and row["successor_ref"].startswith("T") for row in rows)

    imported = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("proyecto_exportado.csv", response.content, "text/csv")},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["counts"]["projects"] == 1
    assert body["counts"]["tasks"] > 0


def test_project_report_pdf_download(client):
    headers = auth_headers(client)
    project_id = client.get("/api/bootstrap", headers=headers).json()["current_project"]["id"]
    response = client.get(f"/api/projects/{project_id}/report/pdf", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].endswith(f"prunin_informe_proyecto_{project_id}.pdf")
    assert response.content.startswith(b"%PDF-1.4")
    assert b"Informe Ejecutivo del Proyecto" in response.content
    assert len(response.content) > 5000


def test_upload_evidence_and_download(client):
    payload = client.get('/api/bootstrap', headers=auth_headers(client)).json()
    project_id = payload['current_project']['id']
    files = {'file': ('acta.txt', b'contenido de prueba', 'text/plain')}
    data = {'project_id': str(project_id), 'entity_type': 'Proyecto', 'uploaded_by': 'PMO', 'description': 'Acta de prueba'}
    response = client.post('/api/evidences/upload', headers=auth_headers(client), data=data, files=files)
    assert response.status_code == 200
    evidence = response.json()
    assert evidence['original_filename'] == 'acta.txt'
    assert "file_path" not in evidence
    assert "stored_filename" not in evidence
    assert evidence["download_url"] == f"/api/evidences/{evidence['id']}/download"
    download = client.get(f"/api/evidences/{evidence['id']}/download", headers=auth_headers(client))
    assert download.status_code == 200
    assert download.content == b'contenido de prueba'
    assert download.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in download.headers["content-disposition"]


def test_bootstrap_does_not_expose_evidence_server_paths(client):
    payload = client.get('/api/bootstrap', headers=auth_headers(client)).json()
    project_id = payload['current_project']['id']
    files = {'file': ('acta.txt', b'contenido de prueba', 'text/plain')}
    client.post('/api/evidences/upload', headers=auth_headers(client), data={'project_id': str(project_id), 'entity_type': 'Proyecto'}, files=files)

    payload = client.get('/api/bootstrap', headers=auth_headers(client)).json()

    assert payload["evidences"]
    assert "file_path" not in payload["evidences"][0]
    assert "stored_filename" not in payload["evidences"][0]


def test_upload_rejects_dangerous_file_type(client):
    payload = client.get('/api/bootstrap', headers=auth_headers(client)).json()
    project_id = payload['current_project']['id']
    files = {'file': ('payload.html', b'<script>alert(1)</script>', 'text/html')}
    data = {'project_id': str(project_id), 'entity_type': 'Proyecto'}

    response = client.post('/api/evidences/upload', headers=auth_headers(client), data=data, files=files)

    assert response.status_code == 400


def test_security_headers_on_protected_api(client):
    response = client.get("/api/bootstrap")

    assert response.status_code == 401
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "script-src 'self'" in response.headers["content-security-policy"]


def test_docs_are_not_public_by_default(client):
    response = client.get("/docs")

    assert response.status_code == 404


def test_i18n_languages_are_public_and_include_top_five(client):
    response = client.get("/api/i18n/languages")

    assert response.status_code == 200
    body = response.json()
    assert body["default_locale"] == "es"
    assert [item["code"] for item in body["languages"]] == ["en", "zh", "hi", "es", "ar"]
    assert all(item["flag"] for item in body["languages"])
    assert {item["dir"] for item in body["languages"]} >= {"ltr", "rtl"}


def test_i18n_catalog_is_public_and_falls_back_to_spanish(client):
    english = client.get("/api/i18n/catalog/en")
    unsupported = client.get("/api/i18n/catalog/fr")

    assert english.status_code == 200
    assert english.json()["messages"]["auth.submit"] == "Sign in"
    assert unsupported.status_code == 200
    assert unsupported.json()["locale"] == "es"
    assert unsupported.json()["messages"]["auth.submit"] == "Ingresar"


def test_i18n_catalogs_share_the_same_keys():
    catalog_dir = Path(__file__).resolve().parents[1] / "static" / "i18n"
    catalogs = {
        path.stem: set(json.loads(path.read_text(encoding="utf-8")).keys())
        for path in catalog_dir.glob("*.json")
    }
    expected = catalogs["es"]

    assert catalogs
    assert all(keys == expected for keys in catalogs.values())
    for locale in catalogs:
        catalog = json.loads((catalog_dir / f"{locale}.json").read_text(encoding="utf-8"))
        assert not [
            key
            for key, value in catalog.items()
            if "??" in str(value) or "\ufffd" in str(value) or str(value).startswith("? ")
        ]


def test_ai_chat_answers_project_state(client):
    project_id = client.get('/api/bootstrap', headers=auth_headers(client)).json()['current_project']['id']
    response = client.post('/api/ai/chat', headers=auth_headers(client), json={'project_id': project_id, 'question': '¿Cómo va el proyecto?'})
    assert response.status_code == 200
    assert 'avance' in response.json()['answer'].lower() or 'estado' in response.json()['answer'].lower()


def test_project_creation_uses_calculated_end_and_currency_catalog(client):
    response = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json=project_required_context(
            name="Proyecto sin fecha fin manual",
            start_date="2026-09-01",
            contractual_end_date="2026-12-31",
            currency="USD",
            budget=1000,
        ),
    )
    assert response.status_code == 200
    project = response.json()
    assert project["end_date"] == "2026-09-01"
    assert project["contractual_end_date"] == "2026-12-31"
    bad = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json=project_required_context(name="Moneda mala", start_date="2026-09-01", currency="dolares"),
    )
    assert bad.status_code == 422


def test_ms_project_task_duration_predecessor_and_outline(client):
    payload = client.get("/api/bootstrap", headers=auth_headers(client)).json()
    project_id = payload["current_project"]["id"]
    first_task = payload["tasks"][0]
    response = client.post(
        "/api/tasks",
        headers=auth_headers(client),
        json={
            "project_id": project_id,
            "title": "Tarea con duración y predecesora",
            "start_date": "2026-07-01",
            "duration_days": 5,
            "predecessor_id": first_task["id"],
            "dependency_type": "FS",
            "lag_days": 1,
        },
    )
    assert response.status_code == 200
    task = response.json()
    assert task["duration_days"] == 5
    assert task["start_date"] >= first_task["end_date"]
    indented = client.post(f"/api/tasks/{task['id']}/indent", headers=auth_headers(client))
    assert indented.status_code == 200
    assert indented.json()["parent_id"] is not None
    outdented = client.post(f"/api/tasks/{task['id']}/outdent", headers=auth_headers(client))
    assert outdented.status_code == 200


def test_scrum_story_can_link_unlink_and_summarize_master_task_by_points(client):
    headers = auth_headers(client)
    payload = client.get("/api/bootstrap", headers=headers).json()
    project_id = payload["current_project"]["id"]
    task_id = payload["tasks"][0]["id"]

    unlinked = client.post(
        "/api/stories",
        headers=headers,
        json={"project_id": project_id, "title": "HU sin vinculo", "status": "Por hacer", "points": 0, "assignee": "Ana", "priority": "Media"},
    )
    done = client.post(
        "/api/stories",
        headers=headers,
        json={"project_id": project_id, "master_task_id": task_id, "title": "HU lista", "status": "Hecho", "points": 5, "assignee": "Ana", "priority": "Alta"},
    )
    pending = client.post(
        "/api/stories",
        headers=headers,
        json={"project_id": project_id, "master_task_id": task_id, "title": "HU pendiente", "status": "Por hacer", "points": 3, "assignee": "Ana", "priority": "Media"},
    )

    assert unlinked.status_code == 200
    assert unlinked.json()["master_task_id"] is None
    assert done.status_code == 200
    assert pending.status_code == 200

    summary = client.get(f"/api/projects/{project_id}/tasks/{task_id}/scrum-summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["stories_total"] == 2
    assert body["points_total"] == 8
    assert body["points_done"] == 5
    assert body["scrum_progress"] == 62

    updated = client.put(
        f"/api/stories/{pending.json()['id']}",
        headers=headers,
        json={"project_id": project_id, "master_task_id": None, "title": "HU desvinculada", "status": "Por hacer", "points": 3, "assignee": "Ana", "priority": "Media"},
    )
    assert updated.status_code == 200
    assert updated.json()["master_task_id"] is None


def test_scrum_summary_falls_back_to_story_count_without_points(client):
    headers = auth_headers(client)
    payload = client.get("/api/bootstrap", headers=headers).json()
    project_id = payload["current_project"]["id"]
    task_id = payload["tasks"][0]["id"]

    client.post("/api/stories", headers=headers, json={"project_id": project_id, "master_task_id": task_id, "title": "HU cero lista", "status": "Hecho", "points": 0, "assignee": "Ana", "priority": "Media"})
    client.post("/api/stories", headers=headers, json={"project_id": project_id, "master_task_id": task_id, "title": "HU cero pendiente", "status": "Por hacer", "points": 0, "assignee": "Ana", "priority": "Media"})

    body = client.get(f"/api/projects/{project_id}/tasks/{task_id}/scrum-summary", headers=headers).json()
    assert body["points_total"] == 0
    assert body["stories_done"] == 1
    assert body["scrum_progress"] == 50


def test_scrum_linkable_tasks_endpoint(client):
    headers = auth_headers(client)
    payload = client.get("/api/bootstrap", headers=headers).json()
    project_id = payload["current_project"]["id"]

    response = client.get(f"/api/projects/{project_id}/scrum/linkable-tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()["tasks"]
    assert {"id", "title", "status", "end_date"}.issubset(response.json()["tasks"][0].keys())


def test_import_csv_links_stories_by_master_task_wbs_and_warns_when_missing(client):
    headers = auth_headers(client)
    csv_data = "\n".join([
        "entity,import_id,name,title,start_date,end_date,duration_days,project_manager,master_task_wbs,sprint_ref,status,points,assignee,priority",
        "project,,Proyecto Scrum CSV,,2026-09-01,2026-09-30,,PM CSV,,,,,,",
        "task,T1,,Actividad Scrum,2026-09-01,,1,,,,,,,",
        "sprint,S1,Sprint CSV,,2026-09-01,2026-09-15,,,,,,,",
        "story,,,HU vinculada,,,,,1,S1,Hecho,5,Ana,Alta",
        "story,,,HU sin vinculo,,,,,9.9,S1,Por hacer,3,Ana,Media",
    ])

    response = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("scrum.csv", BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["stories"] == 2
    assert body["warnings"]
    payload = client.get(f"/api/bootstrap?project_id={body['project_id']}", headers=headers).json()
    linked = next(story for story in payload["stories"] if story["title"] == "HU vinculada")
    unlinked = next(story for story in payload["stories"] if story["title"] == "HU sin vinculo")
    assert linked["master_task_id"] == payload["tasks"][0]["id"]
    assert unlinked["master_task_id"] is None


def test_import_csv_is_idempotent_for_tasks_stories_and_dependencies(client):
    headers = auth_headers(client)
    csv_data = "\n".join([
        "entity,import_id,name,title,start_date,end_date,duration_days,project_manager,master_task_wbs,sprint_ref,status,points,assignee,priority,predecessor_ref,successor_ref,dependency_type",
        "project,,Proyecto Idempotente CSV,,2026-09-01,2026-09-30,,PM CSV,,,,,,,,",
        "task,T1,,Actividad Base,2026-09-01,,1,,,,,,,,,",
        "task,T2,,Actividad Dependiente,2026-09-02,,1,,,,,,,,,",
        "dependency,,,,,,,,,,,,,,T1,T2,FS",
        "sprint,S1,Sprint CSV,,2026-09-01,2026-09-15,,,,,,,,,",
        "story,,,HU vinculada,,,,,1,S1,Hecho,5,Ana,Alta,,,",
    ])

    first = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("idem.csv", BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    second = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("idem.csv", BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    project_id = first.json()["project_id"]
    payload = client.get(f"/api/bootstrap?project_id={project_id}", headers=headers).json()
    assert len([task for task in payload["tasks"] if task["title"] in {"Actividad Base", "Actividad Dependiente"}]) == 2
    assert len([story for story in payload["stories"] if story["title"] == "HU vinculada"]) == 1
    assert len(payload["dependencies"]) == 1
    assert second.json()["summary"]["updated"]["tasks"] >= 2
    assert second.json()["summary"]["updated"]["stories"] >= 1
    assert second.json()["summary"]["skipped"]["dependencies"] >= 1


def test_demo_csv_import_links_scrum_to_master_plan(client):
    headers = auth_headers(client)
    csv_path = Path(__file__).resolve().parents[1] / "proyecto_importacion_completa_demo.csv"

    response = client.post(
        "/api/projects/import/csv",
        headers=headers,
        files={"file": ("proyecto_importacion_completa_demo.csv", csv_path.read_bytes(), "text/csv")},
    )

    assert response.status_code == 200
    payload = client.get(f"/api/bootstrap?project_id={response.json()['project_id']}", headers=headers).json()
    linked = [story for story in payload["stories"] if story["master_task_id"]]
    assert linked
    linked_task_ids = {story["master_task_id"] for story in linked}
    assert any(task["id"] in linked_task_ids for task in payload["tasks"])


def test_critical_path_kpi_matches_marked_tasks(client):
    headers = auth_headers(client)
    payload = client.get("/api/bootstrap", headers=headers).json()

    marked = [task for task in payload["tasks"] if task.get("is_critical_path")]

    assert marked
    assert len(marked) == payload["metrics"]["critical_path_tasks"]


def test_portfolio_summary_endpoint(client):
    response = client.get("/api/portfolio", headers=auth_headers(client))
    assert response.status_code == 200
    rows = response.json()["projects"]
    assert rows
    assert {"name", "project_manager", "progress", "open_risks", "critical_path_tasks"}.issubset(rows[0].keys())


def test_ai_settings_are_saved_and_api_key_is_masked(client):
    response = client.post(
        "/api/ai/settings",
        headers=auth_headers(client),
        json={
            "api_key": "sk-test-secret-abcd",
            "model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Pendiente de prueba"
    assert body["api_key_masked"] == "sk-****abcd"
    assert "sk-test-secret-abcd" not in str(body)


def test_ai_settings_support_multiple_providers(client):
    initial = client.get("/api/ai/settings", headers=auth_headers(client))
    assert "openai" in initial.json()["providers"]
    assert "anthropic" in initial.json()["providers"]
    assert "gemini" in initial.json()["providers"]
    assert initial.json()["providers"]["gemini"]["model_options"]
    assert initial.json()["providers"]["xai"]["model_options"][0]["value"] == "grok-4.5"

    response = client.post(
        "/api/ai/settings",
        headers=auth_headers(client),
        json={
            "provider": "openrouter",
            "api_key": "or-test-secret-abcd",
            "model": "anthropic/claude-sonnet-4.5",
            "config": {"site_url": "https://prunin.local", "app_name": "PRUNIN"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openrouter"
    assert body["status"] == "Pendiente de prueba"
    assert body["provider_name"] == "OpenRouter"
    assert body["model"] == "anthropic/claude-sonnet-4.5"
    assert body["api_key_masked"] == "or-****abcd"
    assert body["config"]["app_name"] == "PRUNIN"
    assert "or-test-secret-abcd" not in str(body)


def test_ai_analysis_snapshot_includes_project_context(client):
    headers = auth_headers(client)
    created = client.post(
        "/api/projects",
        headers=headers,
        json=project_required_context(
            name="Proyecto IA contextual",
            start_date="2026-09-01",
            problem_statement="Brecha de interoperabilidad territorial",
            general_objective="Asegurar interoperabilidad para decisiones tempranas",
            specific_objectives="Objetivo especifico 3: reducir reprocesos",
            objective_indicators="Indicador: tiempo de consolidacion",
            scope_included="Integraciones y tablero",
            scope_excluded="Reemplazo del ERP",
            project_context="Operacion distribuida en regiones",
            stakeholders="Direcciones regionales y PMO",
            constraints="Ventana regulatoria corta",
        ),
    ).json()
    analysis = client.post(f"/api/projects/{created['id']}/ai/analyze", headers=headers, json={})

    assert analysis.status_code == 200
    assert "Objetivo analizado" in analysis.json()["summary"]
    run = client.get(f"/api/ai/analysis-runs/{analysis.json()['run_id']}", headers=headers).json()
    context = run["input_snapshot"]["project_context"]
    assert context["problem_statement"] == "Brecha de interoperabilidad territorial"
    assert context["general_objective"] == "Asegurar interoperabilidad para decisiones tempranas"
    assert context["scope_included"] == "Integraciones y tablero"


def test_ai_provider_replaces_inherited_default_model(client):
    response = client.post(
        "/api/ai/settings",
        headers=auth_headers(client),
        json={
            "provider": "xai",
            "api_key": "xai-test-secret-abcd",
            "model": "gpt-4o-mini",
            "config": {},
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "xai"
    assert response.json()["model"] == "grok-4.5"


def test_ai_connection_without_key_uses_internal_rules_mode(client):
    response = client.post("/api/ai/test-connection", headers=auth_headers(client), json={})

    assert response.status_code == 200
    assert response.json()["mode"] == "internal_rules"
    assert response.json()["status"] == "No configurado"


def test_ai_analysis_uses_internal_rules_when_key_is_not_verified(client):
    headers = auth_headers(client)
    project_id = client.get("/api/bootstrap", headers=headers).json()["current_project"]["id"]
    saved = client.post(
        "/api/ai/settings",
        headers=headers,
        json={"provider": "openai", "api_key": "sk-not-verified", "model": "gpt-4o-mini"},
    )
    response = client.post(f"/api/projects/{project_id}/ai/analyze", headers=headers, json={})

    assert saved.status_code == 200
    assert saved.json()["status"] == "Pendiente de prueba"
    assert response.status_code == 200
    assert response.json()["mode"] == "internal_rules"
    assert response.json()["recommendation_ids"]


def test_ai_internal_rules_analysis_creates_pending_recommendations_and_history(client):
    payload = client.get("/api/bootstrap", headers=auth_headers(client)).json()
    project_id = payload["current_project"]["id"]
    response = client.post(
        f"/api/projects/{project_id}/ai/analyze",
        headers=auth_headers(client),
        json={"include_schedule": True, "include_risks": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert body["recommendation_ids"]
    assert body["mode"] == "internal_rules"
    assert body["engine_label"] == "Motor IA interno v1"
    assert "reglas de PRUNIN" in body["analysis_notice"]

    recs = client.get(f"/api/projects/{project_id}/ai/recommendations", headers=auth_headers(client)).json()["recommendations"]
    assert any(r["status"] == "Pendiente" for r in recs)

    history = client.get(f"/api/projects/{project_id}/ai/history", headers=auth_headers(client)).json()["history"]
    assert history
    assert history[0]["recommendations_count"] >= 1


def test_ai_recommendation_edit_approve_and_apply_rules(client):
    headers = auth_headers(client)
    payload = client.get("/api/bootstrap", headers=headers).json()
    project_id = payload["current_project"]["id"]
    client.post(f"/api/projects/{project_id}/ai/analyze", headers=headers, json={})
    recs = client.get(f"/api/projects/{project_id}/ai/recommendations", headers=headers).json()["recommendations"]
    rec = next(r for r in recs if r["action_type"] == "create_task")

    pending_apply = client.post(f"/api/ai/recommendations/{rec['id']}/apply", headers=headers, json={})
    assert pending_apply.status_code == 400

    edited_payload = {
        "title": "Tarea aprobada desde IA",
        "duration_days": 2,
        "owner": "Ana López",
        "status": "Pendiente",
        "progress": 0,
    }
    edited = client.patch(
        f"/api/ai/recommendations/{rec['id']}",
        headers=headers,
        json={"edited_payload": edited_payload},
    )
    assert edited.status_code == 200
    assert edited.json()["edited_payload"]["title"] == "Tarea aprobada desde IA"

    approved = client.post(f"/api/ai/recommendations/{rec['id']}/approve", headers=headers, json={})
    assert approved.status_code == 200
    assert approved.json()["status"] == "Aprobada"

    before_count = len(client.get("/api/bootstrap", headers=headers).json()["tasks"])
    applied = client.post(f"/api/ai/recommendations/{rec['id']}/apply", headers=headers, json={})
    assert applied.status_code == 200
    assert applied.json()["applied"] is True
    after = client.get("/api/bootstrap", headers=headers).json()
    assert len(after["tasks"]) == before_count + 1
    assert any(t["title"] == "Tarea aprobada desde IA" for t in after["tasks"])

    rec_history = client.get(f"/api/ai/recommendations/{rec['id']}/history", headers=headers).json()["history"]
    assert {h["event_type"] for h in rec_history} >= {"Creada", "Editada", "Aprobada", "Aplicada"}


def test_ai_applied_recommendation_can_be_undone(client):
    headers = auth_headers(client)
    payload = client.get("/api/bootstrap", headers=headers).json()
    project_id = payload["current_project"]["id"]
    client.post(f"/api/projects/{project_id}/ai/analyze", headers=headers, json={})
    recs = client.get(f"/api/projects/{project_id}/ai/recommendations", headers=headers).json()["recommendations"]
    rec = next(r for r in recs if r["action_type"] == "create_task")

    client.post(f"/api/ai/recommendations/{rec['id']}/approve", headers=headers, json={})
    before_count = len(client.get("/api/bootstrap", headers=headers).json()["tasks"])
    applied = client.post(f"/api/ai/recommendations/{rec['id']}/apply", headers=headers, json={})
    assert applied.status_code == 200
    assert len(client.get("/api/bootstrap", headers=headers).json()["tasks"]) == before_count + 1

    undone = client.post(f"/api/ai/recommendations/{rec['id']}/undo", headers=headers, json={})

    assert undone.status_code == 200
    assert undone.json()["undone"] is True
    assert len(client.get("/api/bootstrap", headers=headers).json()["tasks"]) == before_count
    current = client.get(f"/api/ai/recommendations/{rec['id']}", headers=headers).json()
    assert current["status"] == "Aprobada"
    history = client.get(f"/api/ai/recommendations/{rec['id']}/history", headers=headers).json()["history"]
    assert "Deshecha" in {item["event_type"] for item in history}


def test_ai_rejected_recommendation_cannot_be_applied(client):
    headers = auth_headers(client)
    project_id = client.get("/api/bootstrap", headers=headers).json()["current_project"]["id"]
    client.post(f"/api/projects/{project_id}/ai/analyze", headers=headers, json={})
    rec = client.get(f"/api/projects/{project_id}/ai/recommendations", headers=headers).json()["recommendations"][0]

    rejected = client.post(f"/api/ai/recommendations/{rec['id']}/reject", headers=headers, json={})
    apply_response = client.post(f"/api/ai/recommendations/{rec['id']}/apply", headers=headers, json={})

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rechazada"
    assert apply_response.status_code == 400


def test_ai_project_chat_modes(client):
    headers = auth_headers(client)
    project_id = client.get("/api/bootstrap", headers=headers).json()["current_project"]["id"]
    consulta = client.post(
        f"/api/projects/{project_id}/ai/chat",
        headers=headers,
        json={"mode": "consulta", "message": "Como va el proyecto?"},
    )
    accion = client.post(
        f"/api/projects/{project_id}/ai/chat",
        headers=headers,
        json={"mode": "accion", "message": "Analiza el proyecto y propon acciones"},
    )

    assert consulta.status_code == 200
    assert consulta.json()["mode"] == "consulta"
    assert accion.status_code == 200
    assert accion.json()["mode"] == "accion"
    assert accion.json()["recommendation_ids"]


def ai_action_types(result):
    return [item["action_type"] for item in result["recommended_actions"]]


def base_ai_snapshot(metrics=None):
    return {
        "today": "2026-08-07",
        "project": {
            "id": 1,
            "name": "Proyecto prueba IA",
            "project_manager": "PM",
            "budget": 1000,
            "start_date": "2026-07-01",
            "end_date": "2026-08-01",
            "contractual_end_date": "2026-08-30",
            "parameters": {},
        },
        "metrics": {
            "progress": 80,
            "budget": 1000,
            "spent": 600,
            **(metrics or {}),
        },
        "tasks": [],
        "risks": [],
        "deliverables": [],
        "dependencies": [],
        "resources": [],
        "sprints": [],
        "stories": [],
        "conversations": [],
    }


def test_internal_ai_healthy_project_has_no_corrective_actions():
    result = analyze_project_internal_ai(base_ai_snapshot())

    assert result["project_health"] == "Saludable"
    assert ai_action_types(result) == ["no_action"]
    assert result["recommended_actions"][0]["status"] == "Pendiente"


def test_internal_ai_scope_change_is_not_healthy_and_generates_control_action():
    result = analyze_project_internal_ai(base_ai_snapshot({"scope_change_requests": 2}))

    assert result["project_health"] != "Saludable"
    assert "create_deliverable" in ai_action_types(result)


def test_internal_ai_does_not_mix_no_action_with_corrective_actions():
    result = analyze_project_internal_ai(base_ai_snapshot({"scope_change_requests": 1, "deliverables_missing_evidence": 1}))

    action_types = ai_action_types(result)
    assert "no_action" not in action_types


def test_internal_ai_does_not_repeat_action_types():
    result = analyze_project_internal_ai(base_ai_snapshot({
        "overdue_tasks": 2,
        "sprint_velocity_gap": 30,
        "blocked_dependencies": 1,
        "conversation_blockers": 1,
    }))

    action_types = ai_action_types(result)
    assert len(action_types) == len(set(action_types))


def test_internal_ai_high_risk_without_mitigation_generates_mitigation_action():
    snapshot = base_ai_snapshot()
    snapshot["risks"] = [{
        "id": 10,
        "title": "Riesgo alto",
        "level": "Alto",
        "status": "Abierto",
        "mitigation_plan": "",
        "contingency_plan": "Plan de contingencia",
    }]

    result = analyze_project_internal_ai(snapshot)

    assert "add_mitigation_plan" in ai_action_types(result)


def test_internal_ai_high_risk_without_contingency_generates_contingency_action():
    snapshot = base_ai_snapshot()
    snapshot["risks"] = [{
        "id": 11,
        "title": "Riesgo alto",
        "level": "Alto",
        "status": "Abierto",
        "mitigation_plan": "Plan de mitigacion",
        "contingency_plan": "",
    }]

    result = analyze_project_internal_ai(snapshot)

    assert "add_contingency_plan" in ai_action_types(result)


def test_internal_ai_deliverable_without_evidence_generates_request_evidence():
    snapshot = base_ai_snapshot()
    snapshot["deliverables"] = [{
        "id": 20,
        "name": "Entregable vencido",
        "due_date": "2026-08-01",
        "status": "En revision",
        "evidence_url": "",
    }]

    result = analyze_project_internal_ai(snapshot)

    assert "request_evidence" in ai_action_types(result)


def test_internal_ai_budget_ahead_of_progress_generates_financial_risk():
    result = analyze_project_internal_ai(base_ai_snapshot({"progress": 40, "spent": 800}))

    assert "create_risk" in ai_action_types(result)


def test_internal_ai_overdue_tasks_generate_recovery_plan():
    result = analyze_project_internal_ai(base_ai_snapshot({"delayed_tasks": 2}))

    assert "create_task" in ai_action_types(result)


def test_internal_ai_critical_contractual_delay_uses_critical_escalation_title():
    result = analyze_project_internal_ai(base_ai_snapshot({
        "contractual_delay_days": 15,
        "overdue_tasks": 4,
        "critical_tasks": 3,
        "high_risks": 3,
        "risks_without_mitigation": 1,
        "risks_without_contingency": 1,
        "blocked_dependencies": 2,
        "budget_progress_gap": 25,
    }))

    action = next(item for item in result["recommended_actions"] if item["action_type"] == "update_project_status")
    assert result["project_health"] == "Crítico"
    assert action["title"] in {"Escalar proyecto a estado Crítico", "Activar comité ejecutivo de recuperación"}
    assert "Marcar proyecto en riesgo" not in action["title"]
    assert action["proposed_payload"]["status"] == "Crítico"


def test_internal_ai_high_risk_with_plans_generates_medium_executive_alert():
    snapshot = base_ai_snapshot()
    snapshot["risks"] = [{
        "id": 12,
        "title": "Riesgo alto controlado",
        "level": "Alto",
        "status": "Abierto",
        "mitigation_plan": "Plan de mitigacion activo",
        "contingency_plan": "Plan de contingencia activo",
    }]

    result = analyze_project_internal_ai(snapshot)

    action = next(item for item in result["recommended_actions"] if item["action_type"] == "create_alert")
    assert action["title"] == "Seguimiento ejecutivo de riesgos altos"
    assert action["priority"] == "medium"


def test_internal_ai_detects_scrum_gap_linked_to_critical_master_task():
    snapshot = base_ai_snapshot()
    snapshot["tasks"] = [{
        "id": 99,
        "title": "Sprint de componente critico",
        "status": "Crítico",
        "start_date": "2026-07-01",
        "end_date": "2026-08-01",
        "progress": 20,
        "description": "Ejecucion Scrum",
    }]
    snapshot["sprints"] = [{
        "id": 7,
        "name": "Sprint vencido",
        "end_date": "2026-08-01",
        "status": "En curso",
        "velocity": 8,
    }]
    snapshot["stories"] = [{
        "id": 700,
        "project_id": 1,
        "sprint_id": 7,
        "master_task_id": 99,
        "title": "HU critica bloqueada",
        "status": "Bloqueada",
        "points": 5,
    }]

    result = analyze_project_internal_ai(snapshot)

    assert any(issue["type"] == "scrum_critical_delay_gap" for issue in result["detected_issues"])
    assert any(action["action_type"] == "create_alert" for action in result["recommended_actions"])


def test_ai_analyze_endpoint_uses_internal_engine_v1_and_persists_pending_recommendations(client):
    headers = auth_headers(client)
    project_id = client.get("/api/bootstrap", headers=headers).json()["current_project"]["id"]

    response = client.post(f"/api/projects/{project_id}/ai/analyze", headers=headers, json={})

    assert response.status_code == 200
    body = response.json()
    assert body["engine_label"] == "Motor IA interno v1"
    assert body["mode"] == "internal_rules"
    assert body["recommendation_ids"]
    recs = client.get(f"/api/projects/{project_id}/ai/recommendations", headers=headers).json()["recommendations"]
    assert any(r["status"] == "Pendiente" for r in recs)


def test_budget_entries_feed_budget_metrics(client):
    headers = auth_headers(client)
    project = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": "Proyecto con presupuesto mensual",
            "project_manager": "PM Financiero",
            "sponsor": "Sponsor",
            "start_date": "2026-08-01",
            "contractual_end_date": "2026-12-31",
            "budget": 1000,
            "currency": "COP",
        },
    ).json()

    created = client.post(
        "/api/budget-entries",
        headers=headers,
        json={
            "project_id": project["id"],
            "month": "2026-08",
            "category": "Equipo",
            "planned_amount": 400,
            "executed_amount": 500,
            "notes": "Sobreejecucion inicial",
        },
    )

    assert created.status_code == 200
    payload = client.get(f"/api/bootstrap?project_id={project['id']}", headers=headers).json()
    assert payload["budget_entries"][0]["category"] == "Equipo"
    assert payload["metrics"]["budget_source"] == "plan_mensual"
    assert payload["metrics"]["planned_spent"] == 400
    assert payload["metrics"]["spent"] == 500
    assert payload["metrics"]["budget_variance_pp"] == 10

    deleted = client.delete(f"/api/budget-entries/{created.json()['id']}", headers=headers)
    assert deleted.status_code == 200
    payload = client.get(f"/api/bootstrap?project_id={project['id']}", headers=headers).json()
    assert payload["budget_entries"] == []


def test_agile_work_items_replace_scrum_without_breaking_legacy(client):
    headers = auth_headers(client)
    project_id = client.get("/api/bootstrap", headers=headers).json()["current_project"]["id"]

    cycle = client.post(
        "/api/agile-cycles",
        headers=headers,
        json={
            "project_id": project_id,
            "name": "Ciclo Trabajo \u00c1gil",
            "goal": "Validar flujo neutral",
            "start_date": "2026-08-01",
            "end_date": "2026-08-15",
            "status": "Activo",
            "cycle_type": "Scrum",
            "capacity": 13,
        },
    )
    assert cycle.status_code == 200

    neutral = client.post(
        "/api/work-items",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Item neutral sin ciclo obligatorio",
            "description": "Debe funcionar para Kanban o hibrido",
            "work_type": "Tarea",
            "status": "Bloqueado",
            "points": 3,
            "assignee": "Alejandra Trujillo",
            "priority": "Alta",
            "blocked_reason": "Pendiente definicion externa",
        },
    )
    assert neutral.status_code == 200
    body = neutral.json()
    assert body["work_type"] == "Tarea"
    assert body["sprint_id"] is None
    assert body["blocked_reason"] == "Pendiente definicion externa"

    legacy = client.post(
        "/api/stories",
        headers=headers,
        json={
            "project_id": project_id,
            "sprint_id": cycle.json()["id"],
            "title": "Historia legacy absorbida",
            "status": "Por hacer",
            "points": 5,
            "assignee": "Alejandra Trujillo",
            "priority": "Media",
        },
    )
    assert legacy.status_code == 200
    assert legacy.json()["work_type"] == "Historia"

    payload = client.get(f"/api/bootstrap?project_id={project_id}", headers=headers).json()
    assert any(item["title"] == "Item neutral sin ciclo obligatorio" for item in payload["work_items"])
    assert any(item["title"] == "Historia legacy absorbida" for item in payload["stories"])
    assert any(item["name"] == "Ciclo Trabajo \u00c1gil" for item in payload["agile_cycles"])

