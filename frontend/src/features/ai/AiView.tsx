import { AlertTriangle, Bot, CalendarDays, Folder, ShieldCheck, TrendingUp } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import type { AiAnalysisIn } from "@contracts/types";

import { apiRequest } from "@/api/client";
import type { BootstrapPayload } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type Recommendation = {
  id: number;
  title: string;
  description?: string;
  justification?: string;
  priority?: string;
  status?: string;
  action_type?: string;
  target_module?: string;
  expected_impact?: string;
  risk_if_not_done?: string;
  proposed_payload?: Record<string, unknown>;
};

type DetectedIssue = {
  type?: string;
  severity?: string;
  description?: string;
  related_entity_type?: string;
  related_entity_id?: number | null;
  target_module?: string;
};

type AnalysisResult = {
  id?: number;
  project_health?: string;
  summary?: string;
  detected_issues?: DetectedIssue[];
  recommended_actions?: Recommendation[];
  issues?: DetectedIssue[];
  recommendations?: Recommendation[];
  raw_output?: AnalysisResult;
  recommendation_ids?: number[];
  engine_label?: string;
  mode?: string;
};

type AiViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onRecommendationAction: (projectId: number, recommendationId: number, action: "approve" | "reject" | "apply" | "undo") => Promise<void>;
  onRunAnalysis: (projectId: number, include: AiAnalysisIn) => Promise<AnalysisResult | void>;
};

function priorityClass(priority = "") {
  const normalized = priority.toLowerCase();
  if (normalized.includes("high") || normalized.includes("alta")) return "badge danger";
  if (normalized.includes("medium") || normalized.includes("media")) return "badge warning";
  return "badge neutral";
}

function normalizedStatus(status = "") {
  return status.trim().toLowerCase();
}

function statusClass(status = "") {
  const normalized = normalizedStatus(status);
  if (normalized.includes("aplicada")) return "badge success";
  if (normalized.includes("aprobada")) return "badge approved";
  if (normalized.includes("rechazada")) return "badge danger";
  return "badge neutral";
}

function isApplied(recommendation: Recommendation) {
  return normalizedStatus(recommendation.status).includes("aplicada");
}

function isRejected(recommendation: Recommendation) {
  return normalizedStatus(recommendation.status).includes("rechazada");
}

function isApproved(recommendation: Recommendation) {
  return normalizedStatus(recommendation.status).includes("aprobada");
}

export function AiView({ busy = false, canWrite = true, data, onRecommendationAction, onRunAnalysis }: AiViewProps) {
  const { t } = useI18n();
  const [lastRun, setLastRun] = useState<AnalysisResult | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selectedRecommendation, setSelectedRecommendation] = useState<Recommendation | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const normalizeAnalysisRun = useCallback((run: AnalysisResult): AnalysisResult => {
    const raw = run.raw_output || {};
    return {
      ...raw,
      ...run,
      project_health: raw.project_health || run.project_health,
      summary: raw.summary || run.summary,
      detected_issues: run.issues || raw.detected_issues || run.detected_issues || [],
      recommended_actions: run.recommendations || raw.recommended_actions || run.recommended_actions || [],
    };
  }, []);

  const loadLatestAnalysis = useCallback(async () => {
    const list = await apiRequest("list_analysis_runs_api_projects__project_id__ai_analysis_runs_get", {
      params: { project_id: data.current_project.id }
    });
    const runs = ((list as { runs?: AnalysisResult[] }).runs || []);
    if (!runs.length) {
      setLastRun(null);
      return false;
    }
    const latest = runs[0];
    const detail = await apiRequest("get_analysis_run_api_ai_analysis_runs__run_id__get", {
      params: { run_id: Number(latest.id) }
    });
    const normalized = normalizeAnalysisRun(detail as AnalysisResult);
    setLastRun(normalized);
    setRecommendations(normalized.recommended_actions || []);
    return true;
  }, [data.current_project.id, normalizeAnalysisRun]);

  const loadRecommendations = useCallback(async () => {
    const loadedLatest = await loadLatestAnalysis().catch(() => false);
    if (loadedLatest) return;
    const response = await apiRequest("list_recommendations_api_projects__project_id__ai_recommendations_get", {
      params: { project_id: data.current_project.id }
    });
    setRecommendations((response.recommendations as Recommendation[]) || []);
  }, [data.current_project.id, loadLatestAnalysis]);

  useEffect(() => {
    void loadRecommendations().catch(() => setRecommendations([]));
  }, [loadRecommendations]);

  async function runAnalysis() {
    setAnalyzing(true);
    const include: AiAnalysisIn = {
      include_budget: true,
      include_conversations: true,
      include_deliverables: true,
      include_evidences: true,
      include_history: true,
      include_resources: true,
      include_risks: true,
      include_schedule: true,
    };
    try {
      const result = await onRunAnalysis(data.current_project.id, include);
      await loadLatestAnalysis();
      if (result) setLastRun((current) => current || normalizeAnalysisRun(result));
    } finally {
      setAnalyzing(false);
    }
  }

  async function recommendationAction(id: number, action: "approve" | "reject" | "apply" | "undo") {
    await onRecommendationAction(data.current_project.id, id, action);
    await loadRecommendations();
    setSelectedRecommendation((current) => current && current.id === id ? { ...current, status: action === "approve" || action === "undo" ? "Aprobada" : action === "reject" ? "Rechazada" : "Aplicada" } : current);
  }

  const pendingRecommendations = recommendations.filter((item) => String(item.status || "").toLowerCase() === "pendiente");
  const summary = lastRun?.summary || (
    `Ejecuta el análisis para que la IA evalúe el estado del proyecto. Estado actual: avance ${data.metrics.progress}%, ${data.metrics.open_risks} riesgos abiertos, ${data.metrics.delayed_tasks} tareas atrasadas y ${data.metrics.critical_path_tasks} tareas en ruta crítica.`
  );
  const limitedContextNote = "El motor IA utiliza los datos disponibles; si faltan evidencias o conversaciones, las recomendaciones pueden ser menos precisas.";
  const issues = lastRun?.detected_issues || [];
  const executiveSummary = buildExecutiveSummary();

  function friendlyType(value = "") {
    return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) || "Hallazgo";
  }

  function buildExecutiveSummary() {
    if (!lastRun) {
      return [
        `Aun no se ha ejecutado un analisis IA para ${data.current_project.name}. Con la informacion actual, el proyecto registra ${data.metrics.progress}% de avance, ${data.metrics.open_risks} riesgos abiertos, ${data.metrics.delayed_tasks} tarea(s) atrasada(s) y ${data.metrics.critical_path_tasks} tarea(s) en ruta critica.`,
        "Ejecuta el analisis para que el motor revise cronograma, riesgos, recursos, entregables, evidencias, conversaciones e historial, y convierta esas senales en hallazgos y recomendaciones pendientes de aprobacion humana.",
      ];
    }
    const health = lastRun.project_health || data.metrics.health || "Sin clasificar";
    const baseSummary = String(lastRun.summary || "").trim();
    const topIssues = issues.slice(0, 3).map((issue) => issue.description).filter(Boolean);
    const topRecommendations = recommendations.slice(0, 3).map((item) => item.title).filter(Boolean);
    const context = `${data.current_project.name} fue clasificado por la IA en estado ${health}. El analisis combina avance fisico (${data.metrics.progress}%), riesgos abiertos (${data.metrics.open_risks}), tareas atrasadas (${data.metrics.delayed_tasks}) y ruta critica (${data.metrics.critical_path_tasks}) para estimar que tan expuesto esta el proyecto frente a sus compromisos.`;
    const diagnosis = topIssues.length
      ? `Las senales principales son: ${topIssues.join(" ")}`
      : baseSummary || "No se identificaron hallazgos criticos en el ultimo analisis; el proyecto puede mantenerse bajo seguimiento preventivo.";
    const focus = topRecommendations.length
      ? `Como foco de gestion, la IA recomienda priorizar: ${topRecommendations.join("; ")}. Estas acciones permanecen pendientes y no se aplican automaticamente.`
      : "No hay recomendaciones correctivas pendientes; conviene mantener el seguimiento periodico y actualizar evidencias para sostener la trazabilidad.";
    return [context, diagnosis, focus];
  }

  return (
    <section className="section-stack">
      <div className="page-toolbar ai-executive-header">
        <div>
          <h2>{t("ai.title")}</h2>
          <span>{t("ai.description")}</span>
        </div>
        <span className="badge warning">{t("ai.internalActive")}</span>
        {canWrite ? (
          <button className="primary-action compact-action" disabled={busy || analyzing} onClick={() => void runAnalysis()} type="button">
            {busy || analyzing ? "Analizando..." : t("ai.runAnalysis")}
          </button>
        ) : null}
      </div>

      <section className="ai-summary-grid">
        <article className="panel ai-status-card">
          <Bot size={30} />
          <div><span>{t("ai.engine")}</span><strong>{t("ai.internalActive")}</strong></div>
        </article>
        <article className="panel ai-status-card">
          <Folder size={28} />
          <div><span>{t("project.label")}</span><strong>{data.current_project.name}</strong></div>
        </article>
        <article className="panel ai-status-card">
          <ShieldCheck size={28} />
          <div><span>Salud del proyecto</span><strong>{lastRun?.project_health || data.metrics.health}</strong></div>
        </article>
        <article className="panel ai-status-card">
          <TrendingUp size={28} />
          <div><span>{t("kpi.progress")}</span><strong>{data.metrics.progress}%</strong></div>
        </article>
        <article className="panel ai-status-card">
          <AlertTriangle size={28} />
          <div><span>Riesgos del proyecto</span><strong>{data.metrics.open_risks} abiertos / {data.metrics.high_risks} alto</strong></div>
        </article>
        <article className="panel ai-status-card">
          <CalendarDays size={28} />
          <div><span>Recomendaciones pendientes</span><strong>{pendingRecommendations.length}</strong></div>
        </article>
      </section>

      <article className="panel ai-executive-summary">
        <h2>Resumen ejecutivo IA</h2>
        <div className="ai-summary-copy">
          {executiveSummary.map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          <p className="muted-copy"><small>{limitedContextNote}</small></p>
        </div>
      </article>

      <article className="panel">
        <h2>Hallazgos detectados</h2>
        {issues.length ? (
          <div className="ai-issue-grid">
            {issues.map((issue, index) => (
              <article className="ai-issue-card" key={`${issue.type || "issue"}-${index}`}>
                <span className={priorityClass(issue.severity)}>{issue.severity || "Baja"}</span>
                <b>{friendlyType(issue.type)}</b>
                <p title={issue.description}>{issue.description || "Hallazgo detectado por el análisis IA."}</p>
                {(issue.related_entity_type || issue.related_entity_id) ? <small>{issue.related_entity_type || "Entidad"} {issue.related_entity_id || ""}</small> : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="muted-copy">No se identificaron hallazgos críticos en el último análisis.</p>
        )}
      </article>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Recomendaciones IA</h2>
            <span>
              {data.current_project.name} - {recommendations.length ? `${recommendations.length} recomendaciones generadas` : "No hay recomendaciones pendientes."}
            </span>
          </div>
        </div>
        <div className="table-scroll">
          <table className="data-table ai-table">
            <thead><tr><th>Prioridad</th><th>Proyecto</th><th>Acción</th><th>Módulo</th><th>Justificación</th><th>Impacto esperado</th><th>Estado</th><th>Acciones</th></tr></thead>
            <tbody>
              {recommendations.map((recommendation) => (
                <tr className={isApplied(recommendation) ? "ai-applied-row" : ""} key={recommendation.id}>
                  <td><span className={priorityClass(recommendation.priority)}>{recommendation.priority || "-"}</span></td>
                  <td><span className="two-line-text" title={data.current_project.name}>{data.current_project.name}</span></td>
                  <td><strong title={recommendation.title}>{recommendation.title}</strong></td>
                  <td>{recommendation.target_module || recommendation.action_type || "-"}</td>
                  <td><span className="two-line-text" title={recommendation.justification || recommendation.description || "-"}>{recommendation.justification || recommendation.description || "-"}</span></td>
                  <td><span className="two-line-text" title={recommendation.expected_impact || "-"}>{recommendation.expected_impact || "-"}</span></td>
                  <td><span className={statusClass(recommendation.status)}>{recommendation.status || "-"}</span></td>
                  <td className="table-actions">
                    {isApplied(recommendation) ? (
                      <div className="ai-action-group applied-only">
                        {canWrite ? <button className="inline-action ai-action-undo" disabled={busy} onClick={() => void recommendationAction(recommendation.id, "undo")} type="button">Deshacer</button> : null}
                      </div>
                    ) : (
                      <div className="ai-action-group">
                        <button className="inline-action ai-action-view" onClick={() => setSelectedRecommendation(recommendation)} type="button">{t("common.view")}</button>
                        {canWrite ? <button className="inline-action ai-action-approve" disabled={busy || isApproved(recommendation) || isRejected(recommendation)} onClick={() => void recommendationAction(recommendation.id, "approve")} type="button">{t("ai.approve")}</button> : null}
                        {canWrite ? <button className="inline-action ai-action-reject" disabled={busy || isRejected(recommendation)} onClick={() => void recommendationAction(recommendation.id, "reject")} type="button">{t("ai.reject")}</button> : null}
                        {canWrite ? <button className="inline-action ai-action-apply" disabled={busy} onClick={() => void recommendationAction(recommendation.id, "apply")} type="button">{t("ai.apply")}</button> : null}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {!recommendations.length ? <tr><td colSpan={8}>No hay recomendaciones pendientes para {data.current_project.name}.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </div>
      {selectedRecommendation ? (
        <div className="modal-backdrop" onClick={() => setSelectedRecommendation(null)}>
          <section className="ai-detail-modal" onClick={(event) => event.stopPropagation()}>
            <div className="panel-heading">
              <div>
                <h2>{selectedRecommendation.title}</h2>
                <span>{data.current_project.name} - {selectedRecommendation.target_module || selectedRecommendation.action_type || "Proyecto"}</span>
              </div>
              <button className="icon-button" onClick={() => setSelectedRecommendation(null)} type="button">x</button>
            </div>
            <div className="ai-detail-meta">
              <span className={priorityClass(selectedRecommendation.priority)}>{selectedRecommendation.priority || "-"}</span>
              <span className={statusClass(selectedRecommendation.status)}>{selectedRecommendation.status || "-"}</span>
              <span className="badge neutral">{selectedRecommendation.action_type || "Acción"}</span>
            </div>
            <dl className="ai-detail-body">
              <dt>Descripción</dt><dd>{selectedRecommendation.description || "-"}</dd>
              <dt>Justificación</dt><dd>{selectedRecommendation.justification || "-"}</dd>
              <dt>Impacto esperado</dt><dd>{selectedRecommendation.expected_impact || "-"}</dd>
              <dt>Riesgo si no se ejecuta</dt><dd>{selectedRecommendation.risk_if_not_done || "-"}</dd>
              <dt>Payload propuesto</dt><dd><pre>{JSON.stringify(selectedRecommendation.proposed_payload || {}, null, 2)}</pre></dd>
            </dl>
            <div className="form-actions">
              {isApplied(selectedRecommendation) ? (
                canWrite ? <button className="inline-action ai-action-undo" disabled={busy} onClick={() => void recommendationAction(selectedRecommendation.id, "undo")} type="button">Deshacer aplicación</button> : null
              ) : (
                <>
                  {canWrite ? <button className="inline-action ai-action-approve" disabled={busy || isApproved(selectedRecommendation) || isRejected(selectedRecommendation)} onClick={() => void recommendationAction(selectedRecommendation.id, "approve")} type="button">{t("ai.approve")}</button> : null}
                  {canWrite ? <button className="inline-action ai-action-reject" disabled={busy || isRejected(selectedRecommendation)} onClick={() => void recommendationAction(selectedRecommendation.id, "reject")} type="button">{t("ai.reject")}</button> : null}
                  {canWrite ? <button className="primary-action ai-action-apply" disabled={busy} onClick={() => void recommendationAction(selectedRecommendation.id, "apply")} type="button">{t("ai.apply")}</button> : null}
                </>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
