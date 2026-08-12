import { useCallback, useEffect, useState, type ReactNode } from "react";

import type {
  AiAnalysisIn,
  BudgetEntryIn,
  ComponentIn,
  ConversationMessageIn,
  ConversationThreadIn,
  DependencyIn,
  DeliverableIn,
  ProjectIn,
  ProjectUpdate,
  ResourceIn,
  RiskIn,
  StoryIn,
  TaskIn,
  TaskUpdate,
  WorkItemIn
} from "@contracts/types";

import { apiRequest, clearToken, downloadProjectReportPdf, hasToken, logout } from "@/api/client";
import { ProjectShell } from "@/components/ProjectShell";
import { TopBar } from "@/components/TopBar";
import { asBootstrapPayload, type BootstrapPayload, type Story } from "@/domain/project";
import type { AppView } from "@/domain/views";
import { AgileWorkView } from "@/features/agile/AgileWorkView";
import { AiView } from "@/features/ai/AiView";
import { BudgetView } from "@/features/budget/BudgetView";
import { ConversationsView } from "@/features/conversations/ConversationsView";
import { ProjectKpis } from "@/features/dashboard/DashboardView";
import { LoginView } from "@/features/auth/LoginView";
import { KnowledgeView } from "@/features/knowledge/KnowledgeView";
import { MasterPlanView } from "@/features/masterPlan/MasterPlanView";
import { PortfolioView } from "@/features/portfolio/PortfolioView";
import { ResourcesView } from "@/features/resources/ResourcesView";
import { RisksView } from "@/features/risks/RisksView";
import { useI18n } from "@/i18n/i18n";

export function App() {
  const { t } = useI18n();
  const [data, setData] = useState<BootstrapPayload | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [activeView, setActiveView] = useState<AppView>("portfolio");

  const loadBootstrap = useCallback(async (projectId?: number) => {
    if (!hasToken()) return;
    setLoading(true);
    setError("");
    try {
      const response = await apiRequest("bootstrap_api_bootstrap_get", { query: { project_id: projectId } });
      setData(asBootstrapPayload(response));
    } catch (err) {
      clearToken();
      setData(null);
      setError(err instanceof Error ? err.message : "Unable to load project");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  async function handleLogout() {
    await logout().catch(() => clearToken());
    setData(null);
  }

  async function downloadReport() {
    if (!data?.current_project.id) return;
    setReportBusy(true);
    setError("");
    try {
      await downloadProjectReportPdf(data.current_project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo generar el informe PDF");
    } finally {
      setReportBusy(false);
    }
  }

  async function createProject(project: ProjectIn) {
    setSaving(true);
    setError("");
    try {
      const created = await apiRequest("create_project_api_projects_post", { body: project });
      await loadBootstrap(Number(created.id));
      setActiveView("master-plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create project");
    } finally {
      setSaving(false);
    }
  }

  async function updateProject(projectId: number, project: ProjectUpdate) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("update_project_api_projects__project_id__put", { params: { project_id: projectId }, body: project });
      await loadBootstrap(projectId);
      setActiveView("portfolio");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update project");
    } finally {
      setSaving(false);
    }
  }

  async function deleteProject(projectId: number) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("delete_project_api_projects__project_id__delete", { params: { project_id: projectId } });
      await loadBootstrap();
      setActiveView("portfolio");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete project");
    } finally {
      setSaving(false);
    }
  }

  async function importProjectCsv(formData: FormData) {
    setSaving(true);
    setError("");
    try {
      const imported = await apiRequest("import_project_csv_api_projects_import_csv_post", { body: formData });
      const project = imported.project as { id?: number } | undefined;
      const projectId = Number(project?.id || imported.project_id || data?.current_project.id);
      await loadBootstrap(projectId);
      setActiveView("master-plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to import project");
    } finally {
      setSaving(false);
    }
  }

  function openProject(projectId: number) {
    setActiveView("master-plan");
    void loadBootstrap(projectId);
  }

  async function createTask(task: TaskIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_task_api_tasks_post", { body: task });
      await loadBootstrap(task.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create task");
    } finally {
      setSaving(false);
    }
  }

  async function updateTask(taskId: number, task: TaskUpdate) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("update_task_api_tasks__task_id__put", { params: { task_id: taskId }, body: task });
      await loadBootstrap(data?.current_project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update task");
    } finally {
      setSaving(false);
    }
  }

  async function createDependency(dependency: DependencyIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_dependency_api_dependencies_post", { body: dependency });
      await loadBootstrap(dependency.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create dependency");
    } finally {
      setSaving(false);
    }
  }

  async function deleteTask(taskId: number) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("delete_task_api_tasks__task_id__delete", { params: { task_id: taskId } });
      await loadBootstrap(data?.current_project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete task");
    } finally {
      setSaving(false);
    }
  }

  async function moveTaskOutline(taskId: number, direction: "indent" | "outdent") {
    setSaving(true);
    setError("");
    try {
      if (direction === "indent") {
        await apiRequest("indent_task_api_tasks__task_id__indent_post", { params: { task_id: taskId } });
      } else {
        await apiRequest("outdent_task_api_tasks__task_id__outdent_post", { params: { task_id: taskId } });
      }
      await loadBootstrap(data?.current_project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update task outline");
    } finally {
      setSaving(false);
    }
  }

  async function toggleTask(taskId: number) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("toggle_task_api_tasks__task_id__toggle_post", { params: { task_id: taskId } });
      await loadBootstrap(data?.current_project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to toggle task");
    } finally {
      setSaving(false);
    }
  }

  async function createRisk(risk: RiskIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_risk_api_risks_post", { body: risk });
      await loadBootstrap(risk.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create risk");
    } finally {
      setSaving(false);
    }
  }

  async function createResource(resource: ResourceIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_resource_api_resources_post", { body: resource });
      await loadBootstrap(resource.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create resource");
    } finally {
      setSaving(false);
    }
  }

  async function createBudgetEntry(entry: BudgetEntryIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_budget_entry_api_budget_entries_post", { body: entry });
      await loadBootstrap(entry.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create budget entry");
    } finally {
      setSaving(false);
    }
  }

  async function deleteBudgetEntry(entryId: number) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("delete_budget_entry_api_budget_entries__entry_id__delete", { params: { entry_id: entryId } });
      await loadBootstrap(data?.current_project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete budget entry");
    } finally {
      setSaving(false);
    }
  }

  async function createStory(story: StoryIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_story_api_stories_post", { body: story });
      await loadBootstrap(story.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create story");
    } finally {
      setSaving(false);
    }
  }

  async function createWorkItem(item: WorkItemIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_work_item_api_work_items_post", { body: item });
      await loadBootstrap(item.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create work item");
    } finally {
      setSaving(false);
    }
  }

  async function updateStory(story: Story) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("update_story_api_stories__story_id__put", {
        params: { story_id: story.id },
        body: {
          project_id: story.project_id,
          sprint_id: story.sprint_id,
          master_task_id: story.master_task_id ?? null,
          component_id: story.component_id ?? null,
          deliverable_id: story.deliverable_id ?? null,
          title: story.title,
          description: story.description || "",
          work_type: story.work_type || "Historia",
          status: story.status,
          points: story.points,
          assignee: story.assignee,
          priority: story.priority,
          blocked_reason: story.blocked_reason || "",
          started_at: story.started_at || "",
          completed_at: story.completed_at || "",
          labels: story.labels || [],
          board_order: story.board_order || 0,
        },
      });
      await loadBootstrap(story.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update story");
    } finally {
      setSaving(false);
    }
  }

  async function updateWorkItem(item: Story) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("update_work_item_api_work_items__item_id__put", {
        params: { item_id: item.id },
        body: {
          project_id: item.project_id,
          sprint_id: item.sprint_id ?? null,
          master_task_id: item.master_task_id ?? null,
          component_id: item.component_id ?? null,
          deliverable_id: item.deliverable_id ?? null,
          title: item.title,
          description: item.description || "",
          work_type: item.work_type || "Historia",
          status: item.status,
          points: item.points,
          assignee: item.assignee,
          priority: item.priority,
          blocked_reason: item.blocked_reason || "",
          started_at: item.started_at || "",
          completed_at: item.completed_at || "",
          labels: item.labels || [],
          board_order: item.board_order || 0,
        },
      });
      await loadBootstrap(item.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update work item");
    } finally {
      setSaving(false);
    }
  }

  async function createConversation(thread: ConversationThreadIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_conversation_api_conversations_post", { body: thread });
      await loadBootstrap(thread.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create conversation");
    } finally {
      setSaving(false);
    }
  }

  async function createConversationMessage(threadId: number, message: ConversationMessageIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_conversation_message_api_conversations__thread_id__messages_post", {
        params: { thread_id: threadId },
        body: message
      });
      await loadBootstrap(message.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create message");
    } finally {
      setSaving(false);
    }
  }

  async function createComponent(component: ComponentIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_component_api_components_post", { body: component });
      await loadBootstrap(component.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create component");
    } finally {
      setSaving(false);
    }
  }

  async function createDeliverable(deliverable: DeliverableIn) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("create_deliverable_api_deliverables_post", { body: deliverable });
      await loadBootstrap(deliverable.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create deliverable");
    } finally {
      setSaving(false);
    }
  }

  async function uploadEvidence(formData: FormData, projectId: number) {
    setSaving(true);
    setError("");
    try {
      await apiRequest("upload_evidence_api_evidences_upload_post", { body: formData });
      await loadBootstrap(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload evidence");
    } finally {
      setSaving(false);
    }
  }

  async function runAiAnalysis(projectId: number, include: AiAnalysisIn) {
    setSaving(true);
    setError("");
    try {
      const response = await apiRequest("analyze_project_api_projects__project_id__ai_analyze_post", {
        params: { project_id: projectId },
        body: include
      });
      await loadBootstrap(projectId);
      return response;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run AI analysis");
    } finally {
      setSaving(false);
    }
  }

  async function actOnRecommendation(projectId: number, recommendationId: number, action: "approve" | "reject" | "apply" | "undo") {
    setSaving(true);
    setError("");
    try {
      if (action === "approve") {
        await apiRequest("approve_recommendation_api_ai_recommendations__recommendation_id__approve_post", { params: { recommendation_id: recommendationId } });
      } else if (action === "reject") {
        await apiRequest("reject_recommendation_api_ai_recommendations__recommendation_id__reject_post", { params: { recommendation_id: recommendationId } });
      } else if (action === "undo") {
        await apiRequest("undo_recommendation_api_ai_recommendations__recommendation_id__undo_post", { params: { recommendation_id: recommendationId } });
      } else {
        await apiRequest("apply_recommendation_api_ai_recommendations__recommendation_id__apply_post", { params: { recommendation_id: recommendationId } });
      }
      await loadBootstrap(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update recommendation");
    } finally {
      setSaving(false);
    }
  }

  function renderView(payload: BootstrapPayload) {
    const canWrite = payload.current_user?.role !== "Consulta";
    function withKpis(children: ReactNode) {
      return (
        <>
          <ProjectKpis data={payload} />
          {children}
        </>
      );
    }

    if (activeView === "master-plan") {
      return withKpis(
        <MasterPlanView
          busy={saving}
          data={payload}
          onCreateTask={createTask}
          onDeleteTask={deleteTask}
          onCreateDependency={createDependency}
          onIndentTask={(taskId) => moveTaskOutline(taskId, "indent")}
          onOutdentTask={(taskId) => moveTaskOutline(taskId, "outdent")}
          onToggleTask={toggleTask}
          onUpdateTask={updateTask}
          onCreateStory={createStory}
          onUpdateStory={updateStory}
          canWrite={canWrite}
        />
      );
    }
    if (activeView === "scrum") return withKpis(<AgileWorkView busy={saving} canWrite={canWrite} data={payload} onCreateWorkItem={createWorkItem} onUpdateWorkItem={updateWorkItem} />);
    if (activeView === "resources") return withKpis(<ResourcesView busy={saving} canWrite={canWrite} data={payload} onCreateResource={createResource} />);
    if (activeView === "budget") return withKpis(<BudgetView busy={saving} canWrite={canWrite} data={payload} onCreateBudgetEntry={createBudgetEntry} onDeleteBudgetEntry={deleteBudgetEntry} />);
    if (activeView === "risks") return withKpis(<RisksView busy={saving} canWrite={canWrite} data={payload} onCreateRisk={createRisk} />);
    if (activeView === "conversations") {
      return withKpis(
        <ConversationsView
          busy={saving}
          canWrite={canWrite}
          data={payload}
          onCreateMessage={createConversationMessage}
          onCreateThread={createConversation}
        />
      );
    }
    if (activeView === "knowledge") {
      return withKpis(
        <KnowledgeView
          busy={saving}
          canWrite={canWrite}
          data={payload}
          onCreateComponent={createComponent}
          onCreateDeliverable={createDeliverable}
          onUploadEvidence={uploadEvidence}
        />
      );
    }
    if (activeView === "ai") return withKpis(<AiView busy={saving} canWrite={canWrite} data={payload} onRecommendationAction={actOnRecommendation} onRunAnalysis={runAiAnalysis} />);
    return (
      <PortfolioView
        busy={saving}
        canWrite={canWrite}
        data={payload}
        onCreateProject={createProject}
        onUpdateProject={updateProject}
        onDeleteProject={deleteProject}
        onImportProjectCsv={importProjectCsv}
        onOpenProject={openProject}
      />
    );
  }

  if (!hasToken() || !data) {
    return <LoginView onAuthenticated={() => void loadBootstrap()} />;
  }

  return (
    <>
      <TopBar activeView={activeView} user={data.current_user} onViewChange={setActiveView} onLogout={() => void handleLogout()} />
      {error ? <p className="app-message error-text">{error}</p> : null}
      {loading ? (
        <p className="app-message">{t("project.loading")}</p>
      ) : (
        <ProjectShell
          activeView={activeView}
          data={data}
          loading={loading}
          reportBusy={reportBusy}
          onDownloadReport={() => void downloadReport()}
          onProjectChange={(projectId) => void loadBootstrap(projectId)}
        >
          {renderView(data)}
        </ProjectShell>
      )}
    </>
  );
}
