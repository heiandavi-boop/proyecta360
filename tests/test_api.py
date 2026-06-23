import pytest
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app_module.DB_PATH = tmp_path / "proyecta360_test.db"
    with TestClient(app_module.app) as c:
        yield c


def test_bootstrap_seeds_default_project(client):
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["projects"]
    assert payload["current_project"]["name"] == "Plataforma Cliente 360"


def test_rejects_invalid_task_progress(client):
    project_id = client.get("/api/bootstrap").json()["current_project"]["id"]
    response = client.post(
        "/api/tasks",
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
    first = client.get("/api/bootstrap").json()
    first_project_id = first["current_project"]["id"]
    first_task_id = first["tasks"][0]["id"]
    second_project_id = client.post(
        "/api/projects",
        json={
            "name": "Proyecto B",
            "start_date": "2026-07-01",
            "end_date": "2026-08-01",
        },
    ).json()["id"]
    second_task_id = client.post(
        "/api/tasks",
        json={
            "project_id": second_project_id,
            "title": "Tarea B",
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
        },
    ).json()["id"]
    response = client.post(
        "/api/dependencies",
        json={
            "project_id": first_project_id,
            "predecessor_id": first_task_id,
            "successor_id": second_task_id,
        },
    )

    assert response.status_code == 400


def test_rejects_dependency_cycle(client):
    payload = client.get("/api/bootstrap").json()
    project_id = payload["current_project"]["id"]
    first_task_id = payload["tasks"][0]["id"]
    new_task_id = client.post(
        "/api/tasks",
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
        json={
            "project_id": project_id,
            "predecessor_id": new_task_id,
            "successor_id": first_task_id,
        },
    )

    assert response.status_code == 400
