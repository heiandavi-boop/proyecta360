import json
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]


def test_openapi_contract_snapshot_matches_application():
    expected = json.loads((ROOT / "contracts" / "api" / "openapi.json").read_text(encoding="utf-8"))
    current = app_module.app.openapi()

    assert expected["openapi"] == current["openapi"]
    assert expected["info"] == current["info"]
    assert set(expected["paths"]) == set(current["paths"])
    assert set(expected["components"]["schemas"]) == set(current["components"]["schemas"])


def test_typescript_contract_contains_core_frontend_operations():
    types = (ROOT / "contracts" / "api" / "types.ts").read_text(encoding="utf-8")
    endpoints = (ROOT / "contracts" / "api" / "endpoints.ts").read_text(encoding="utf-8")

    assert "export interface ProjectIn" in types
    assert "export interface TaskIn" in types
    assert "export interface AiAnalysisIn" in types
    assert "bootstrap_api_bootstrap_get" in endpoints
    assert "analyze_project_api_projects__project_id__ai_analyze_post" in endpoints
    assert '"file": File' in types
