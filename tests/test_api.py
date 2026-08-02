import pytest
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app_module.DB_PATH = tmp_path / "proyecta360_test.db"
    with TestClient(app_module.app) as c:
        yield c


def auth_headers(client, email="admin@proyecta360.local", password="admin123"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}



def test_bootstrap_requires_session(client):
    response = client.get("/api/bootstrap")

    assert response.status_code == 401

def test_bootstrap_seeds_default_project(client):
    response = client.get("/api/bootstrap", headers=auth_headers(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload["projects"]
    assert payload["current_project"]["name"] == "Proyecta360 LAC"
    assert payload["components"]
    assert payload["deliverables"]
    assert payload["history"]
    assert payload["conversation_threads"]
    assert payload["conversation_messages"]
    assert payload["intelligence"]["recommendations"]


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
        json={
            "name": "Proyecto B",
            "start_date": "2026-07-01",
            "end_date": "2026-08-01",
        },
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
        json={
            "name": "Proyecto financiado B",
            "start_date": "2026-07-01",
            "end_date": "2026-08-01",
        },
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
        json={
            "name": "Proyecto colaborativo B",
            "start_date": "2026-07-01",
            "end_date": "2026-08-01",
        },
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
    response = client.post('/api/auth/login', json={'email':'admin@proyecta360.local','password':'admin123'})
    assert response.status_code == 200
    token = response.json()['token']
    me = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['user']['role'] == 'Administrador'


def test_login_hashes_token_and_migrates_password(client):
    response = client.post("/api/auth/login", json={"email": "admin@proyecta360.local", "password": "admin123"})
    assert response.status_code == 200
    token = response.json()["token"]

    with app_module.db() as conn:
        user = app_module.one(conn, "SELECT * FROM users WHERE email = ?", ("admin@proyecta360.local",))

    assert user["access_token"] == ""
    assert user["access_token_hash"]
    assert user["access_token_hash"] != token
    assert user["password_hash"].startswith("pbkdf2_sha256$")
    assert user["token_expires_at"]


def test_auth_login_accepts_browser_form_fallback(client):
    response = client.post(
        "/api/auth/login",
        data={"email": "admin@proyecta360.local", "password": "admin123"},
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
        headers=auth_headers(client, "consulta@proyecta360.local", "consulta123"),
        json={"name": "No permitido", "start_date": "2026-09-01"},
    )

    assert response.status_code == 403


def test_export_json_contains_full_project(client):
    project_id = client.get('/api/bootstrap', headers=auth_headers(client)).json()['current_project']['id']
    response = client.get(f'/api/projects/{project_id}/export/json', headers=auth_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload['project']['id'] == project_id
    assert payload['components']
    assert payload['tasks']
    assert 'evidences' in payload


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


def test_ai_chat_answers_project_state(client):
    project_id = client.get('/api/bootstrap', headers=auth_headers(client)).json()['current_project']['id']
    response = client.post('/api/ai/chat', headers=auth_headers(client), json={'project_id': project_id, 'question': '¿Cómo va el proyecto?'})
    assert response.status_code == 200
    assert 'avance' in response.json()['answer'].lower() or 'estado' in response.json()['answer'].lower()


def test_project_creation_uses_calculated_end_and_currency_catalog(client):
    response = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json={
            "name": "Proyecto sin fecha fin manual",
            "start_date": "2026-09-01",
            "contractual_end_date": "2026-12-31",
            "currency": "USD",
            "budget": 1000,
        },
    )
    assert response.status_code == 200
    project = response.json()
    assert project["end_date"] == "2026-09-01"
    assert project["contractual_end_date"] == "2026-12-31"
    bad = client.post(
        "/api/projects",
        headers=auth_headers(client),
        json={"name": "Moneda mala", "start_date": "2026-09-01", "currency": "dolares"},
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


def test_portfolio_summary_endpoint(client):
    response = client.get("/api/portfolio", headers=auth_headers(client))
    assert response.status_code == 200
    rows = response.json()["projects"]
    assert rows
    assert {"name", "project_manager", "progress", "open_risks", "critical_path_tasks"}.issubset(rows[0].keys())

