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
            "config": {"site_url": "https://proyecta360.local", "app_name": "Proyecta360"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openrouter"
    assert body["status"] == "Pendiente de prueba"
    assert body["provider_name"] == "OpenRouter"
    assert body["model"] == "anthropic/claude-sonnet-4.5"
    assert body["api_key_masked"] == "or-****abcd"
    assert body["config"]["app_name"] == "Proyecta360"
    assert "or-test-secret-abcd" not in str(body)


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
    assert body["engine_label"] == "Motor interno"
    assert "reglas de Proyecta360" in body["analysis_notice"]

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

