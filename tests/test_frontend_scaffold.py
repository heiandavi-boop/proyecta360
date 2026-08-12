import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_frontend_react_shell_exists():
    expected = [
        "package.json",
        "vite.config.ts",
        "tsconfig.json",
        "index.html",
        "src/main.tsx",
        "src/App.tsx",
        "src/api/client.ts",
        "src/components/ProjectShell.tsx",
        "src/domain/views.ts",
        "src/i18n/i18n.tsx",
        "src/features/auth/LoginView.tsx",
        "src/features/ai/AiView.tsx",
        "src/features/conversations/ConversationsView.tsx",
        "src/features/dashboard/DashboardView.tsx",
        "src/features/knowledge/KnowledgeView.tsx",
        "src/features/masterPlan/MasterPlanView.tsx",
        "src/features/portfolio/PortfolioView.tsx",
        "src/features/resources/ResourcesView.tsx",
        "src/features/risks/RisksView.tsx",
        "src/features/scrum/ScrumView.tsx",
    ]

    assert all((FRONTEND / path).exists() for path in expected)


def test_frontend_package_scripts_and_contract_usage():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    client = (FRONTEND / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    tsconfig = json.loads((FRONTEND / "tsconfig.json").read_text(encoding="utf-8"))

    assert package["scripts"]["dev"].startswith("vite")
    assert "react" in package["dependencies"]
    assert "typescript" in package["devDependencies"]
    assert "@contracts/*" in tsconfig["compilerOptions"]["paths"]
    assert '@contracts/endpoints' in client
    assert "ApiOperationMap" in client


def test_frontend_phase_3_shell_has_navigation_and_project_selection():
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    topbar = (FRONTEND / "src" / "components" / "TopBar.tsx").read_text(encoding="utf-8")
    shell = (FRONTEND / "src" / "components" / "ProjectShell.tsx").read_text(encoding="utf-8")
    views = (FRONTEND / "src" / "domain" / "views.ts").read_text(encoding="utf-8")

    assert "activeView" in app
    assert "query: { project_id: projectId }" in app
    assert "APP_VIEWS.map" in topbar
    assert "onProjectChange" in shell
    assert '"portfolio"' in views
    assert '"master-plan"' in views
    assert '"ai"' in views


def test_frontend_phase_4_has_operational_project_and_task_flows():
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    portfolio = (FRONTEND / "src" / "features" / "portfolio" / "PortfolioView.tsx").read_text(encoding="utf-8")
    master_plan = (FRONTEND / "src" / "features" / "masterPlan" / "MasterPlanView.tsx").read_text(encoding="utf-8")

    assert "create_project_api_projects_post" in app
    assert "import_project_csv_api_projects_import_csv_post" in app
    assert "create_task_api_tasks_post" in app
    assert "onCreateProject" in portfolio
    assert "onImportProjectCsv" in portfolio
    assert "onOpenProject" in portfolio
    assert "onCreateTask" in master_plan
    assert "TaskIn" in master_plan


def test_frontend_portfolio_is_project_open_list_not_metric_table():
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    portfolio = (FRONTEND / "src" / "features" / "portfolio" / "PortfolioView.tsx").read_text(encoding="utf-8")

    assert "portfolio-table" in portfolio
    assert "filter-bar" in portfolio
    assert "portfolio.methodology" not in portfolio
    assert "delete-project-modal" in portfolio
    assert "deleteInput.trim() !== deleteCode" in portfolio
    assert "PHS" in portfolio
    assert "progress_variance_pp" in portfolio
    assert "budget_variance_pp" in portfolio
    assert "<DashboardView" not in app
    assert "ProjectKpis data={payload}" in app


def test_frontend_phase_5_has_master_plan_task_operations():
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    master_plan = (FRONTEND / "src" / "features" / "masterPlan" / "MasterPlanView.tsx").read_text(encoding="utf-8")

    assert "update_task_api_tasks__task_id__put" in app
    assert "create_dependency_api_dependencies_post" in app
    assert "toggle_task_api_tasks__task_id__toggle_post" in app
    assert "delete_task_api_tasks__task_id__delete" in app
    assert "indent_task_api_tasks__task_id__indent_post" in app
    assert "outdent_task_api_tasks__task_id__outdent_post" in app
    assert "onUpdateTask" in master_plan
    assert "onDeleteTask" in master_plan
    assert "onCreateDependency" in master_plan
    assert "selectTaskForDependency" in master_plan
    assert "recalculateSchedule" in master_plan
    assert "expandedTimeline" in master_plan
    assert "onToggleTask" in master_plan
    assert "row-menu-trigger" in master_plan
    assert "runMenuAction" in master_plan
    assert "Agregar subtarea" in master_plan
    assert "ownerOptions" in master_plan
    assert "data.resources.map((resource) => resource.name)" in master_plan
    assert "gantt-shell" in master_plan
    assert "gantt-calendar-head" in master_plan
    assert "gantt-inspector" in master_plan
    assert "dependency-line" in master_plan
    assert "gantt-bar" in master_plan


def test_frontend_phase_6_has_domain_create_flows():
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    scrum = (FRONTEND / "src" / "features" / "scrum" / "ScrumView.tsx").read_text(encoding="utf-8")
    resources = (FRONTEND / "src" / "features" / "resources" / "ResourcesView.tsx").read_text(encoding="utf-8")
    risks = (FRONTEND / "src" / "features" / "risks" / "RisksView.tsx").read_text(encoding="utf-8")

    assert "create_story_api_stories_post" in app
    assert "update_story_api_stories__story_id__put" in app
    assert "create_resource_api_resources_post" in app
    assert "create_risk_api_risks_post" in app
    assert "onCreateStory" in scrum
    assert "onUpdateStory" in scrum
    assert "draggable={canWrite && !busy}" in scrum
    assert "onColumnDragStart" in scrum
    assert "statusOrderStorageKey" in scrum
    assert "application/x-prunin-column" in scrum
    assert "kanban-status-form" in scrum
    assert "burndown-card" in scrum
    assert "burndown-actual" in scrum
    assert "onCreateResource" in resources
    assert "onCreateRisk" in risks
    assert "data-table" in resources
    assert "data-table" in risks


def test_frontend_final_migration_covers_remaining_operational_modules():
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    client = (FRONTEND / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    ai = (FRONTEND / "src" / "features" / "ai" / "AiView.tsx").read_text(encoding="utf-8")
    conversations = (FRONTEND / "src" / "features" / "conversations" / "ConversationsView.tsx").read_text(encoding="utf-8")
    knowledge = (FRONTEND / "src" / "features" / "knowledge" / "KnowledgeView.tsx").read_text(encoding="utf-8")

    assert "create_conversation_api_conversations_post" in app
    assert "create_conversation_message_api_conversations__thread_id__messages_post" in app
    assert "create_component_api_components_post" in app
    assert "create_deliverable_api_deliverables_post" in app
    assert "upload_evidence_api_evidences_upload_post" in app
    assert "analyze_project_api_projects__project_id__ai_analyze_post" in app
    assert "apply_recommendation_api_ai_recommendations__recommendation_id__apply_post" in app
    assert "undo_recommendation_api_ai_recommendations__recommendation_id__undo_post" in app
    assert "instanceof FormData" in client
    assert "onCreateThread" in conversations
    assert "onUploadEvidence" in knowledge
    assert "onRunAnalysis" in ai
    assert "ai-executive-header" in ai
    assert "ai-table" in ai


def test_fastapi_root_prefers_react_dist_when_available():
    app_factory = (ROOT / "proyecta360" / "app_factory.py").read_text(encoding="utf-8")

    assert 'base_dir / "frontend" / "dist"' in app_factory
    assert 'app.mount("/assets"' in app_factory
    assert 'base_dir / "static" / "index.html"' not in app_factory


def test_legacy_static_ui_files_removed_after_react_migration():
    legacy_files = [
        ROOT / "static" / "index.html",
        ROOT / "static" / "app.js",
        ROOT / "static" / "styles.css",
        ROOT / "static" / "i18n.js",
    ]

    assert not any(path.exists() for path in legacy_files)


def test_frontend_readonly_permissions_and_critical_path_visibility():
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    portfolio = (FRONTEND / "src" / "features" / "portfolio" / "PortfolioView.tsx").read_text(encoding="utf-8")
    master_plan = (FRONTEND / "src" / "features" / "masterPlan" / "MasterPlanView.tsx").read_text(encoding="utf-8")
    scrum = (FRONTEND / "src" / "features" / "scrum" / "ScrumView.tsx").read_text(encoding="utf-8")
    ai = (FRONTEND / "src" / "features" / "ai" / "AiView.tsx").read_text(encoding="utf-8")

    assert 'role !== "Consulta"' in app
    assert "canWrite ? (" in portfolio
    assert "canWrite && showForm" in master_plan
    assert "Ver ruta crítica" in master_plan
    assert "critical-path-badge" in master_plan
    assert "is_critical_path" in master_plan
    assert "draggable={canWrite && !busy}" in scrum
    assert "canWrite ? <button" in ai
