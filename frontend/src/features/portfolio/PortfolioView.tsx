import { useMemo, useState, type FormEvent } from "react";

import type { ProjectIn, ProjectUpdate } from "@contracts/types";

import type { BootstrapPayload } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type PortfolioViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateProject: (project: ProjectIn) => Promise<void>;
  onUpdateProject: (projectId: number, project: ProjectUpdate) => Promise<void>;
  onImportProjectCsv: (formData: FormData) => Promise<void>;
  onOpenProject: (projectId: number) => void;
};

type PortfolioRow = {
  project_id?: number;
  name?: string;
  project_manager?: string;
  methodology?: string;
  start_date?: string;
  end_date?: string;
  health?: string;
  status?: string;
  progress?: number;
  expected_progress?: number;
  progress_variance_pp?: number;
  spent?: number;
  planned_spent?: number;
  budget_executed_percent?: number;
  budget_expected_percent?: number;
  budget_variance_pp?: number;
  phs?: number;
  schedule_score?: number;
  budget_score?: number;
  risk_score?: number;
  currency?: string;
  open_risks?: number;
  critical_path_tasks?: number;
  at_risk_milestones?: number;
  next_milestone?: { title?: string; end_date?: string } | null;
};

type ProjectDraft = ProjectIn & { id?: number };
type SectionId = "general" | "problem" | "scope" | "context" | "planning";

const sections: Array<{ id: SectionId; label: string }> = [
  { id: "general", label: "General" },
  { id: "problem", label: "Problema" },
  { id: "scope", label: "Alcance" },
  { id: "context", label: "Contexto" },
  { id: "planning", label: "Planificacion" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function money(value: unknown) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function signed(value: unknown, suffix = " pp") {
  const number = Number(value || 0);
  return `${number > 0 ? "+" : ""}${number.toFixed(1)}${suffix}`;
}

function signalClass(value: unknown, inverted = false) {
  const number = Number(value || 0);
  if (inverted ? number > 5 : number < -5) return "signal danger";
  if (inverted ? number > 0 : number < 0) return "signal warning";
  return "signal success";
}

function badgeClass(value: string) {
  const normalized = value.toLowerCase();
  if (normalized.includes("crit")) return "badge danger";
  if (normalized.includes("riesgo") || normalized.includes("alto")) return "badge warning";
  if (normalized.includes("salud") || normalized.includes("cerrado")) return "badge success";
  return "badge neutral";
}

function defaultDraft(): ProjectDraft {
  return {
    name: "",
    project_code: "",
    description: "",
    sponsor: "",
    project_manager: "",
    requesting_area: "",
    project_type: "",
    methodology: "Hibrida",
    status: "Planeado",
    start_date: todayIso(),
    contractual_end_date: "",
    budget: 0,
    currency: "COP",
    problem_statement: "",
    current_situation: "",
    consequence_if_not_done: "",
    general_objective: "",
    specific_objectives: "",
    objective_indicators: "",
    scope_included: "",
    scope_excluded: "",
    success_criteria: "",
    assumptions: "",
    constraints: "",
    project_context: "",
    political_context: "",
    geographic_context: "",
    socioeconomic_context: "",
    cultural_context: "",
    institutional_context: "",
    stakeholders: "",
    external_dependencies: "",
    regulatory_constraints: "",
  } as ProjectDraft;
}

function projectToDraft(project: Record<string, unknown>): ProjectDraft {
  return { ...defaultDraft(), ...(project as Partial<ProjectDraft>), id: Number(project.id) };
}

export function PortfolioView({ busy = false, canWrite = true, data, onCreateProject, onUpdateProject, onImportProjectCsv, onOpenProject }: PortfolioViewProps) {
  const { t } = useI18n();
  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState<number | null>(null);
  const [activeSection, setActiveSection] = useState<SectionId>("general");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [draft, setDraft] = useState<ProjectDraft>(() => defaultDraft());

  const rows = data.portfolio as PortfolioRow[];
  const filteredRows = useMemo(() => rows.filter((row) => {
    const text = `${row.name || ""} ${row.project_manager || ""} ${row.methodology || ""}`.toLowerCase();
    const matchesQuery = !query || text.includes(query.toLowerCase());
    const rowStatus = String(row.health || row.status || "");
    const matchesStatus = !statusFilter || rowStatus === statusFilter;
    return matchesQuery && matchesStatus;
  }), [query, rows, statusFilter]);
  const statusOptions = Array.from(new Set(rows.map((row) => String(row.health || row.status || "")).filter(Boolean)));
  const canSaveProject = Boolean(
    draft.name.trim() &&
    draft.project_manager?.trim() &&
    draft.sponsor?.trim() &&
    draft.methodology?.trim() &&
    draft.start_date &&
    draft.currency &&
    Number(draft.budget) >= 0
  );

  async function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSaveProject) return;
    if (editingProjectId) {
      await onUpdateProject(editingProjectId, draft);
    } else {
      await onCreateProject(draft);
    }
    setShowCreatePanel(false);
    setEditingProjectId(null);
    setActiveSection("general");
    setDraft(defaultDraft());
  }

  function editProject(projectId: number) {
    const project = data.projects.find((item) => item.id === projectId);
    if (!project) return;
    setDraft(projectToDraft(project as unknown as Record<string, unknown>));
    setEditingProjectId(projectId);
    setActiveSection("general");
    setShowCreatePanel(true);
  }

  function updateDraft<K extends keyof ProjectDraft>(key: K, value: ProjectDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csvFile) return;
    const formData = new FormData();
    formData.set("file", csvFile);
    await onImportProjectCsv(formData);
    setShowCreatePanel(false);
    setCsvFile(null);
  }

  return (
    <section className="section-stack">
      <div className="page-toolbar">
        <div>
          <h2>{t("portfolio.title")}</h2>
          <span>{t("portfolio.count", { count: filteredRows.length })}</span>
        </div>
        {canWrite ? (
          <button className="primary-action compact-action" disabled={busy} onClick={() => setShowCreatePanel((value) => !value)} type="button">
            {t("project.new")}
          </button>
        ) : null}
      </div>

      {showCreatePanel ? (
        <div className="import-panel">
          <form className="stack-form" onSubmit={(event) => void submitProject(event)}>
            <h3>{editingProjectId ? "Editar proyecto" : t("project.createManual")}</h3>
            <div className="segmented-tabs" role="tablist">
              {sections.map((section) => <button className={activeSection === section.id ? "active-tool" : ""} key={section.id} onClick={() => setActiveSection(section.id)} type="button">{section.label}</button>)}
            </div>
            {activeSection === "general" ? (
              <div className="form-grid two">
                <label>{t("common.name")}<input required value={draft.name} onChange={(event) => updateDraft("name", event.target.value)} /></label>
                <label>Codigo del proyecto<input value={draft.project_code || ""} onChange={(event) => updateDraft("project_code", event.target.value)} /></label>
                <label>{t("project.manager")}<input required value={draft.project_manager || ""} onChange={(event) => updateDraft("project_manager", event.target.value)} /></label>
                <label>{t("project.sponsor")}<input required value={draft.sponsor || ""} onChange={(event) => updateDraft("sponsor", event.target.value)} /></label>
                <label>Area solicitante / cliente<input value={draft.requesting_area || ""} onChange={(event) => updateDraft("requesting_area", event.target.value)} /></label>
                <label>Tipo de proyecto<input value={draft.project_type || ""} onChange={(event) => updateDraft("project_type", event.target.value)} /></label>
                <label>Metodologia<select required value={draft.methodology || "Hibrida"} onChange={(event) => updateDraft("methodology", event.target.value)}><option>Tradicional</option><option>Scrum</option><option>Kanban</option><option>Hibrida</option></select></label>
                <label className="wide-field">{t("common.description")}<textarea rows={3} value={draft.description || ""} onChange={(event) => updateDraft("description", event.target.value)} /></label>
              </div>
            ) : null}
            {activeSection === "problem" ? (
              <div className="form-grid two">
                <p className="tab-description wide-field">Define la necesidad que origina el proyecto y por que es necesario ejecutarlo.</p>
                <label className="wide-field">Problema o brecha<textarea rows={4} placeholder="Describe la brecha o necesidad que justifica ejecutar el proyecto." value={draft.problem_statement || ""} onChange={(event) => updateDraft("problem_statement", event.target.value)} /></label>
                <label className="wide-field">Situacion actual<textarea rows={3} placeholder="Describe las condiciones actuales relacionadas con el problema. Puedes incluir datos o evidencias relevantes." value={draft.current_situation || ""} onChange={(event) => updateDraft("current_situation", event.target.value)} /></label>
                <label className="wide-field">Consecuencia de no ejecutar el proyecto<textarea rows={3} placeholder="Que consecuencias tendria mantener la situacion actual." value={draft.consequence_if_not_done || ""} onChange={(event) => updateDraft("consequence_if_not_done", event.target.value)} /></label>
              </div>
            ) : null}
            {activeSection === "scope" ? (
              <div className="form-grid two">
                <p className="tab-description wide-field">Define que busca lograr el proyecto, que incluye y como se medira su exito.</p>
                <label className="wide-field">Objetivo general<textarea rows={3} value={draft.general_objective || ""} onChange={(event) => updateDraft("general_objective", event.target.value)} /></label>
                <label className="wide-field">Objetivos especificos<textarea rows={4} placeholder="Incluye objetivos numerados si aplica." value={draft.specific_objectives || ""} onChange={(event) => updateDraft("specific_objectives", event.target.value)} /></label>
                <label className="wide-field">Indicadores por objetivo<textarea rows={4} placeholder="Relaciona cada objetivo con sus indicadores." value={draft.objective_indicators || ""} onChange={(event) => updateDraft("objective_indicators", event.target.value)} /></label>
                <label>Alcance incluido<textarea rows={3} placeholder="Que productos, resultados, actividades o componentes forman parte del proyecto?" value={draft.scope_included || ""} onChange={(event) => updateDraft("scope_included", event.target.value)} /></label>
                <label>Fuera de alcance<textarea rows={3} placeholder="Que elementos quedan explicitamente fuera del proyecto?" value={draft.scope_excluded || ""} onChange={(event) => updateDraft("scope_excluded", event.target.value)} /></label>
                <label>Criterios de exito<textarea rows={3} placeholder="Que condicion debe cumplirse para considerar exitoso el proyecto?" value={draft.success_criteria || ""} onChange={(event) => updateDraft("success_criteria", event.target.value)} /></label>
                <label>Supuestos<textarea rows={3} placeholder="Que condiciones asumimos que se mantendran para que el proyecto pueda ejecutarse?" value={draft.assumptions || ""} onChange={(event) => updateDraft("assumptions", event.target.value)} /></label>
                <label>Restricciones<textarea rows={3} placeholder="Que limites condicionan lo que el proyecto puede hacer?" value={draft.constraints || ""} onChange={(event) => updateDraft("constraints", event.target.value)} /></label>
              </div>
            ) : null}
            {activeSection === "context" ? (
              <div className="form-grid two">
                <p className="tab-description wide-field">Describe brevemente el entorno del proyecto y los factores externos que pueden influir en su ejecucion.</p>
                <label className="wide-field">Contexto del proyecto<textarea rows={4} value={draft.project_context || ""} onChange={(event) => updateDraft("project_context", event.target.value)} /></label>
                <p className="form-group-label wide-field">Entorno</p>
                <label>Aspectos politicos<textarea rows={3} value={draft.political_context || ""} onChange={(event) => updateDraft("political_context", event.target.value)} /></label>
                <label>Aspectos geograficos<textarea rows={3} value={draft.geographic_context || ""} onChange={(event) => updateDraft("geographic_context", event.target.value)} /></label>
                <label>Aspectos socioeconomicos<textarea rows={3} value={draft.socioeconomic_context || ""} onChange={(event) => updateDraft("socioeconomic_context", event.target.value)} /></label>
                <label>Aspectos culturales<textarea rows={3} value={draft.cultural_context || ""} onChange={(event) => updateDraft("cultural_context", event.target.value)} /></label>
                <label>Aspectos institucionales<textarea rows={3} value={draft.institutional_context || ""} onChange={(event) => updateDraft("institutional_context", event.target.value)} /></label>
                <p className="form-group-label wide-field">Relaciones y condicionantes</p>
                <label>Partes interesadas<textarea rows={3} value={draft.stakeholders || ""} onChange={(event) => updateDraft("stakeholders", event.target.value)} /></label>
                <label>Dependencias externas<textarea rows={3} value={draft.external_dependencies || ""} onChange={(event) => updateDraft("external_dependencies", event.target.value)} /></label>
                <label>Requisitos o restricciones regulatorias<textarea rows={3} value={draft.regulatory_constraints || ""} onChange={(event) => updateDraft("regulatory_constraints", event.target.value)} /></label>
              </div>
            ) : null}
            {activeSection === "planning" ? (
              <div className="form-grid two">
                <p className="tab-description wide-field">Define fechas, presupuesto y elementos necesarios para ejecutar el proyecto.</p>
                <label>{t("project.startDate")}<input required type="date" value={draft.start_date} onChange={(event) => updateDraft("start_date", event.target.value)} /></label>
                <label>Fecha de finalizacion prevista<input type="date" value={draft.contractual_end_date || ""} onChange={(event) => updateDraft("contractual_end_date", event.target.value)} /></label>
                <label>{t("project.currency")}<select value={draft.currency || "COP"} onChange={(event) => updateDraft("currency", event.target.value)}><option value="COP">COP</option><option value="USD">USD</option><option value="EUR">EUR</option><option value="MXN">MXN</option><option value="PEN">PEN</option><option value="CLP">CLP</option><option value="BRL">BRL</option></select></label>
                <label>Presupuesto total<input min="0" type="number" value={draft.budget || 0} onChange={(event) => updateDraft("budget", Number(event.target.value))} /></label>
              </div>
            ) : null}
            <div className="form-actions"><button className="icon-button" onClick={() => { setShowCreatePanel(false); setEditingProjectId(null); setDraft(defaultDraft()); }} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy || !canSaveProject} type="submit">{busy ? t("common.saving") : editingProjectId ? "Guardar cambios" : t("project.create")}</button></div>
          </form>

          {!editingProjectId ? <form className="stack-form import-card" onSubmit={(event) => void submitImport(event)}>
            <h3>{t("project.importCsv")}</h3>
            <p className="muted-copy">{t("project.importCsvHelp")}</p>
            <label>{t("project.csvFile")}<input accept=".csv,text/csv" required type="file" onChange={(event) => setCsvFile(event.target.files?.[0] || null)} /></label>
            <p className="muted-copy">{t("project.csvHelp")}</p>
            <div className="form-actions"><button className="icon-button" onClick={() => setShowCreatePanel(false)} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy || !csvFile} type="submit">{busy ? t("common.saving") : t("project.import")}</button></div>
          </form> : null}
        </div>
      ) : null}

      <div className="panel">
        <div className="filter-bar">
          <input aria-label="Buscar proyectos" placeholder="Buscar proyecto o PM" value={query} onChange={(event) => setQuery(event.target.value)} />
          <select aria-label="Filtrar estado" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">Todos los estados</option>
            {statusOptions.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </div>
        <div className="table-scroll">
          <table className="data-table portfolio-table">
            <thead>
              <tr>
                <th>{t("portfolio.project")}</th>
                <th>PM</th>
                <th>{t("portfolio.start")}</th>
                <th>{t("portfolio.calculatedEnd")}</th>
                <th>{t("portfolio.status")}</th>
                <th>PHS</th>
                <th>Avance real / esperado</th>
                <th>Presupuesto ejec. / esperado</th>
                <th className="optional-col">{t("portfolio.currency")}</th>
                <th>Hitos en riesgo</th>
                <th className="optional-col">Proximo hito</th>
                <th>{t("ai.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, index) => {
                const status = String(row.health || row.status || "");
                return (
                  <tr key={`${row.project_id || row.name}-${index}`}>
                    <td><strong>{row.name}</strong></td>
                    <td>{row.project_manager || "-"}</td>
                    <td>{row.start_date || "-"}</td>
                    <td>{row.end_date || "-"}</td>
                    <td><span className={badgeClass(status)}>{status || "-"}</span></td>
                    <td><strong>{Number(row.phs || 0).toFixed(1)}</strong><small className="score-breakdown">C {row.schedule_score || 0} · P {row.budget_score || 0} · R {row.risk_score || 0}</small></td>
                    <td><div className="progress-cell"><i style={{ width: `${Number(row.progress || 0)}%` }} /><span>{row.progress || 0}% / {row.expected_progress || 0}%</span></div><small className={signalClass(row.progress_variance_pp)}>{signed(row.progress_variance_pp)}</small></td>
                    <td><span>{Number(row.budget_executed_percent || 0).toFixed(1)}% / {Number(row.budget_expected_percent || 0).toFixed(1)}%</span><small className={signalClass(row.budget_variance_pp, true)}>{signed(row.budget_variance_pp)}</small><small>{money(row.spent)} de {money(row.planned_spent)}</small></td>
                    <td className="optional-col">{row.currency || "-"}</td>
                    <td>{row.at_risk_milestones || 0}<small>{row.critical_path_tasks || 0} criticas</small></td>
                    <td className="optional-col">{row.next_milestone?.title || "-"}<small>{row.next_milestone?.end_date || ""}</small></td>
                    <td>
                      <button className="inline-action" disabled={busy || !row.project_id} onClick={() => onOpenProject(Number(row.project_id))} type="button">{t("portfolio.open")}</button>
                      {canWrite ? <button className="inline-action" disabled={busy || !row.project_id} onClick={() => editProject(Number(row.project_id))} type="button">Editar</button> : null}
                    </td>
                  </tr>
                );
              })}
              {!filteredRows.length ? <tr><td colSpan={12}>{t("common.noData")}</td></tr> : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
