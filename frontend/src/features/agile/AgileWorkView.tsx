import { useEffect, useMemo, useState, type CSSProperties, type DragEvent, type FormEvent } from "react";

import type { WorkItemIn } from "@contracts/types";

import type { BootstrapPayload, Story, Task } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type AgileWorkViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateWorkItem: (item: WorkItemIn) => Promise<void>;
  onUpdateWorkItem: (item: Story) => Promise<void>;
};

type AgileMode = "Scrum" | "Kanban" | "Scrumban" | "Híbrido";
type AgileTab = "list" | "board" | "metrics" | "settings";

const DEFAULT_STATUSES = ["Lista", "Por hacer", "En progreso", "En revisión", "Bloqueado", "Hecho"];
const MODE_STATUS_PRESETS: Record<AgileMode, string[]> = {
  Scrum: ["Backlog", "Seleccionado", "En desarrollo", "En revisión", "Bloqueado", "Hecho"],
  Kanban: ["Entrada", "Listo", "En curso", "Validación", "Bloqueado", "Terminado"],
  Scrumban: ["Backlog", "Listo", "En curso", "En revisión", "Bloqueado", "Hecho"],
  Híbrido: ["Planificado", "Por hacer", "En progreso", "En revisión", "Bloqueado", "Cerrado"],
};
const MODE_PROFILES: Record<AgileMode, {
  focus: string;
  planning: string;
  board: string;
  metric: string;
  cadence: string;
  accent: string;
}> = {
  Scrum: {
    focus: "Entrega por ciclos con compromiso de alcance y objetivo de sprint.",
    planning: "Se prioriza un ciclo activo y se mide avance por puntos comprometidos.",
    board: "Backlog -> Seleccionado -> Desarrollo -> Revisión -> Hecho.",
    metric: "Burndown, velocidad y cumplimiento del sprint.",
    cadence: "Sprint fijo",
    accent: "#2764E8",
  },
  Kanban: {
    focus: "Flujo continuo sin ciclos obligatorios, optimizado por WIP y bloqueos.",
    planning: "El trabajo entra por demanda y se limita lo que está en curso.",
    board: "Entrada -> Listo -> En curso -> Validación -> Terminado.",
    metric: "WIP, throughput, bloqueos y tiempo de flujo.",
    cadence: "Flujo continuo",
    accent: "#14b8a6",
  },
  Scrumban: {
    focus: "Combina cadencia de Scrum con control de flujo de Kanban.",
    planning: "Puede usar ciclos, pero protege el tablero con límites y priorización continua.",
    board: "Backlog -> Listo -> En curso -> Revisión -> Hecho.",
    metric: "WIP más avance por ciclo y entregables terminados.",
    cadence: "Ciclo flexible",
    accent: "#7654E8",
  },
  Híbrido: {
    focus: "Conecta trabajo ágil con Plan Maestro, PMO, entregables y gobierno.",
    planning: "El trabajo se prioriza por componentes, hitos y dependencias del cronograma.",
    board: "Planificado -> Por hacer -> En progreso -> Revisión -> Cerrado.",
    metric: "Trazabilidad al Plan Maestro, avance, bloqueos y entregables.",
    cadence: "Gobierno mixto",
    accent: "#171A21",
  },
};
const WORK_TYPES = ["Historia", "Tarea", "Bug", "Mejora", "Solicitud", "Entregable", "Otro"];
const AGILE_MODES: AgileMode[] = ["Scrum", "Kanban", "Scrumban", "Híbrido"];

function burndownPoints(total: number, done: number) {
  const width = 520;
  const height = 150;
  const remaining = Math.max(0, total - done);
  return {
    ideal: `20,20 ${width - 20},${height - 25}`,
    actual: `20,20 ${width * 0.35},${Math.max(35, height - 25 - done * 8)} ${width * 0.68},${Math.max(45, height - 25 - done * 4)} ${width - 20},${Math.max(25, height - 25 - remaining * 6)}`,
    width,
    height,
  };
}

function uniquePeople(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean))).sort((left, right) => left.localeCompare(right));
}

function orderStatuses(statuses: string[], preferredOrder: string[]) {
  const known = preferredOrder.filter((status) => statuses.includes(status));
  const missing = statuses.filter((status) => !known.includes(status));
  return [...known, ...missing];
}

function taskWbsCodes(tasks: Task[]) {
  const counters: number[] = [];
  return tasks.map((task) => {
    const level = Math.max(0, Number(task.outline_level || (task.parent_id ? 1 : 0)));
    if (level > 0 && !counters[0]) counters[0] = 1;
    counters[level] = (counters[level] || 0) + 1;
    counters.length = level + 1;
    return counters.join(".");
  });
}

function isDone(status: string) {
  return ["hecho", "done", "completado", "cerrado"].includes(status.toLowerCase());
}

function isActive(status: string) {
  const normalized = status.toLowerCase();
  return normalized.includes("progreso") || normalized.includes("revisión") || normalized.includes("revision") || normalized === "bloqueado";
}

function modeFromProject(data: BootstrapPayload): AgileMode {
  const parameters = data.current_project.parameters || {};
  const configured = String(parameters.selected_execution_methodology || parameters.agile_mode || data.current_project.methodology || "");
  const match = AGILE_MODES.find((mode) => configured.toLowerCase().includes(mode.toLowerCase()));
  return match || "Híbrido";
}

export function AgileWorkView({ busy = false, canWrite = true, data, onCreateWorkItem, onUpdateWorkItem }: AgileWorkViewProps) {
  const { t } = useI18n();
  const statusStorageKey = `prunin.agile.statuses.${data.current_project.id}`;
  const statusOrderStorageKey = `prunin.agile.statusOrder.${data.current_project.id}`;
  const modeStorageKey = `prunin.agile.mode.${data.current_project.id}`;
  const [customStatuses, setCustomStatuses] = useState<string[]>([]);
  const [statusOrder, setStatusOrder] = useState<string[]>([]);
  const [newStatus, setNewStatus] = useState("");
  const [draggingItemId, setDraggingItemId] = useState<number | null>(null);
  const [draggingStatus, setDraggingStatus] = useState("");
  const [dragOverStatus, setDragOverStatus] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [activeTab, setActiveTab] = useState<AgileTab>("board");
  const [mode, setMode] = useState<AgileMode>(() => modeFromProject(data));
  const [selectedCycleId, setSelectedCycleId] = useState<number | "all">("all");
  const modeProfile = MODE_PROFILES[mode];
  const modePreset = MODE_STATUS_PRESETS[mode];

  const baseStatuses = useMemo(() => Array.from(new Set([
    ...modePreset,
    ...customStatuses,
    ...data.stories.map((item) => item.status || "Por hacer"),
  ].filter(Boolean))), [customStatuses, data.stories, modePreset]);
  const statuses = useMemo(() => orderStatuses(baseStatuses, statusOrder.length ? statusOrder : modePreset), [baseStatuses, modePreset, statusOrder]);
  const usesCycles = mode === "Scrum" || mode === "Scrumban" || mode === "Híbrido";
  const activeCycle = data.sprints.find((cycle) => cycle.status === "Activo") || data.sprints[0];
  const visibleItems = useMemo(() => {
    if (mode === "Scrum") {
      const cycleId = selectedCycleId === "all" ? activeCycle?.id : selectedCycleId;
      return cycleId ? data.stories.filter((item) => item.sprint_id === cycleId) : data.stories;
    }
    return data.stories;
  }, [activeCycle?.id, data.stories, mode, selectedCycleId]);

  const totalPoints = visibleItems.reduce((sum, item) => sum + Number(item.points || 0), 0);
  const completedPoints = visibleItems.filter((item) => isDone(item.status)).reduce((sum, item) => sum + Number(item.points || 0), 0);
  const chart = useMemo(() => burndownPoints(totalPoints, completedPoints), [totalPoints, completedPoints]);
  const cyclePercent = totalPoints ? Math.round((completedPoints / totalPoints) * 100) : 0;
  const wipCount = visibleItems.filter((item) => isActive(item.status)).length;
  const blockedCount = visibleItems.filter((item) => item.status === "Bloqueado").length;
  const throughput = visibleItems.filter((item) => isDone(item.status)).length;

  const ownerOptions = useMemo(() => uniquePeople([
    data.current_project.project_manager,
    ...data.resources.map((resource) => resource.name),
    ...data.tasks.map((task) => task.owner),
    ...data.risks.map((risk) => risk.owner),
    ...data.components.map((component) => component.owner),
    ...data.deliverables.map((deliverable) => deliverable.owner),
    ...data.stories.map((item) => item.assignee),
  ]), [data.components, data.current_project.project_manager, data.deliverables, data.resources, data.risks, data.stories, data.tasks]);

  const taskCodes = useMemo(() => taskWbsCodes(data.tasks), [data.tasks]);
  const taskLabels = useMemo(() => new Map(data.tasks.map((task, index) => [
    task.id,
    `${taskCodes[index]} ${task.title}`,
  ])), [data.tasks, taskCodes]);
  const taskOptions = useMemo(() => data.tasks.map((task, index) => ({
    task,
    label: `${taskCodes[index]} ${task.title} - Fin: ${task.end_date || task.start_date} - ${task.status || "Pendiente"}`,
  })), [data.tasks, taskCodes]);

  const [draft, setDraft] = useState<WorkItemIn>({
    project_id: data.current_project.id,
    title: "",
    description: "",
    work_type: "Tarea",
    status: "Lista",
    points: 1,
    assignee: "",
    priority: "Media",
    sprint_id: null,
    master_task_id: null,
    component_id: null,
    deliverable_id: null,
    blocked_reason: "",
    started_at: "",
    completed_at: "",
    labels: [],
    board_order: 0,
  });

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(statusStorageKey);
      setCustomStatuses(stored ? JSON.parse(stored) as string[] : []);
      const storedOrder = window.localStorage.getItem(statusOrderStorageKey);
      setStatusOrder(storedOrder ? JSON.parse(storedOrder) as string[] : []);
      const storedMode = window.localStorage.getItem(modeStorageKey) as AgileMode | null;
      if (storedMode && AGILE_MODES.includes(storedMode)) setMode(storedMode);
    } catch {
      setCustomStatuses([]);
      setStatusOrder([]);
    }
  }, [modeStorageKey, statusOrderStorageKey, statusStorageKey]);

  function persistCustomStatuses(nextStatuses: string[]) {
    setCustomStatuses(nextStatuses);
    window.localStorage.setItem(statusStorageKey, JSON.stringify(nextStatuses));
  }

  function persistStatusOrder(nextOrder: string[]) {
    setStatusOrder(nextOrder);
    window.localStorage.setItem(statusOrderStorageKey, JSON.stringify(nextOrder));
  }

  function updateMode(nextMode: AgileMode) {
    setMode(nextMode);
    window.localStorage.setItem(modeStorageKey, nextMode);
    const defaultOrCurrent = new Set([...DEFAULT_STATUSES, ...Object.values(MODE_STATUS_PRESETS).flat()]);
    const hasOnlyDefaultStatuses = statuses.every((status) => defaultOrCurrent.has(status));
    if (!statusOrder.length || hasOnlyDefaultStatuses) {
      persistStatusOrder(MODE_STATUS_PRESETS[nextMode]);
      setDraft((current) => ({ ...current, status: MODE_STATUS_PRESETS[nextMode][0], sprint_id: nextMode === "Kanban" ? null : current.sprint_id }));
    }
    setActiveTab(nextMode === "Scrum" ? "metrics" : "board");
  }

  function createStatus(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const status = newStatus.trim();
    if (!status || statuses.includes(status)) return;
    persistCustomStatuses([...customStatuses, status]);
    persistStatusOrder([...statuses, status]);
    setDraft((current) => ({ ...current, status }));
    setNewStatus("");
  }

  function onDragStart(event: DragEvent<HTMLElement>, itemId: number) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-prunin-work-item", String(itemId));
    setDraggingItemId(itemId);
  }

  function onColumnDragStart(event: DragEvent<HTMLElement>, status: string) {
    event.stopPropagation();
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-prunin-column", status);
    setDraggingStatus(status);
  }

  function onDropColumn(targetStatus: string) {
    const sourceStatus = draggingStatus;
    setDraggingStatus("");
    setDragOverStatus("");
    if (!canWrite || !sourceStatus || sourceStatus === targetStatus || busy) return;
    const currentOrder = orderStatuses(baseStatuses, statuses);
    const sourceIndex = currentOrder.indexOf(sourceStatus);
    const targetIndex = currentOrder.indexOf(targetStatus);
    if (sourceIndex < 0 || targetIndex < 0) return;
    const nextOrder = [...currentOrder];
    const [moved] = nextOrder.splice(sourceIndex, 1);
    nextOrder.splice(targetIndex, 0, moved);
    persistStatusOrder(nextOrder);
  }

  async function onDropItem(event: DragEvent<HTMLElement>, status: string) {
    event.preventDefault();
    if (Array.from(event.dataTransfer.types).includes("application/x-prunin-column")) {
      onDropColumn(status);
      return;
    }
    setDragOverStatus("");
    const itemId = Number(event.dataTransfer.getData("application/x-prunin-work-item") || draggingItemId);
    const item = data.stories.find((entry) => entry.id === itemId);
    setDraggingItemId(null);
    if (!canWrite || !item || item.status === status || busy) return;
    await onUpdateWorkItem({
      ...item,
      status,
      blocked_reason: status === "Bloqueado" && !item.blocked_reason ? t("agile.blockedDefault") : item.blocked_reason,
    });
  }

  async function submitItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateWorkItem({ ...draft, project_id: data.current_project.id });
    setShowForm(false);
    setDraft((current) => ({ ...current, title: "", description: "", points: 1, blocked_reason: "", master_task_id: null }));
  }

  function renderCard(item: Story) {
    return (
      <div
        className={`story-card agile-work-card${draggingItemId === item.id ? " dragging" : ""}${item.status === "Bloqueado" ? " blocked" : ""}`}
        draggable={canWrite && !busy}
        key={item.id}
        onDragEnd={() => {
          setDraggingItemId(null);
          setDragOverStatus("");
        }}
        onDragStart={(event) => onDragStart(event, item.id)}
      >
        <div className="agile-card-topline">
          <span className="badge neutral">{item.work_type || "Historia"}</span>
          <small>{item.priority}</small>
        </div>
        <b>{item.title}</b>
        <span>{item.assignee || t("knowledge.noOwner")}</span>
        {item.master_task_id ? <small className="story-plan-link">Plan Maestro: {taskLabels.get(item.master_task_id) || `Tarea ${item.master_task_id}`}</small> : null}
        {item.blocked_reason ? <small className="agile-blocked-reason">{item.blocked_reason}</small> : null}
        <small>{item.points} {t("story.points")}</small>
      </div>
    );
  }

  return (
    <section className={`panel full-span agile-workspace agile-mode-${mode.toLowerCase().replace("í", "i")}`} style={{ "--mode-accent": modeProfile.accent } as CSSProperties}>
      <div className="panel-heading agile-heading">
        <div>
          <h2>{t("agile.title")}</h2>
          <span>{t("agile.description")}</span>
        </div>
        <div className="agile-heading-actions">
          <label>
            {t("agile.mode")}
            <select value={mode} onChange={(event) => updateMode(event.target.value as AgileMode)}>
              {AGILE_MODES.map((entry) => <option key={entry} value={entry}>{entry}</option>)}
            </select>
          </label>
          {canWrite ? (
            <button className="primary-action compact-action" disabled={busy} onClick={() => setShowForm((value) => !value)} type="button">
              {t("workItem.new")}
            </button>
          ) : null}
        </div>
      </div>

      <div className="agile-mode-banner">
        <article>
          <span>Marco activo</span>
          <b>{mode}</b>
          <small>{modeProfile.cadence}</small>
        </article>
        <article>
          <span>Foco operativo</span>
          <b>{modeProfile.focus}</b>
          <small>{modeProfile.planning}</small>
        </article>
        <article>
          <span>Flujo recomendado</span>
          <b>{modeProfile.board}</b>
          <small>{modeProfile.metric}</small>
        </article>
      </div>

      <div className="agile-tabs" role="tablist" aria-label={t("agile.title")}>
        {([
          ["board", t("agile.board")],
          ["list", t("agile.workList")],
          ["metrics", t("agile.metrics")],
          ["settings", t("agile.settings")],
        ] as Array<[AgileTab, string]>).map(([tab, label]) => (
          <button className={activeTab === tab ? "active" : ""} key={tab} onClick={() => setActiveTab(tab)} type="button">{label}</button>
        ))}
      </div>

      {canWrite && showForm ? (
        <form className="inline-form agile-item-form" onSubmit={(event) => void submitItem(event)}>
          <label className="wide-field">{t("workItem.title")}<input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          <label>{t("workItem.type")}<select value={draft.work_type || "Tarea"} onChange={(event) => setDraft({ ...draft, work_type: event.target.value })}>{WORK_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
          <label>{t("common.status")}<select value={draft.status || "Lista"} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>{statuses.map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
          <label>{t("agile.cycle")}<select disabled={!usesCycles} value={draft.sprint_id || ""} onChange={(event) => setDraft({ ...draft, sprint_id: event.target.value ? Number(event.target.value) : null })}><option value="">{usesCycles ? t("agile.noCycle") : t("agile.cyclesDisabled")}</option>{data.sprints.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name} - {cycle.status}</option>)}</select></label>
          <label>{t("story.points")}<input min="0" type="number" value={draft.points || 0} onChange={(event) => setDraft({ ...draft, points: Number(event.target.value) })} /></label>
          <label>{t("common.owner")}<select value={draft.assignee || ""} onChange={(event) => setDraft({ ...draft, assignee: event.target.value })}><option value="">{t("knowledge.noOwner")}</option>{ownerOptions.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select></label>
          <label>{t("story.priority")}<select value={draft.priority || "Media"} onChange={(event) => setDraft({ ...draft, priority: event.target.value })}><option value="Alta">{t("story.high")}</option><option value="Media">{t("story.medium")}</option><option value="Baja">{t("story.low")}</option></select></label>
          <label className="wide-field">{t("agile.masterPlanLink")}<select value={draft.master_task_id || ""} onChange={(event) => setDraft({ ...draft, master_task_id: event.target.value ? Number(event.target.value) : null })}><option value="">{t("agile.noMasterPlanLink")}</option>{taskOptions.map(({ task, label }) => <option key={task.id} value={task.id}>{label}</option>)}</select></label>
          <label>{t("agile.component")}<select value={draft.component_id || ""} onChange={(event) => setDraft({ ...draft, component_id: event.target.value ? Number(event.target.value) : null })}><option value="">{t("agile.noComponent")}</option>{data.components.map((component) => <option key={component.id} value={component.id}>{component.name}</option>)}</select></label>
          <label>{t("agile.deliverable")}<select value={draft.deliverable_id || ""} onChange={(event) => setDraft({ ...draft, deliverable_id: event.target.value ? Number(event.target.value) : null })}><option value="">{t("agile.noDeliverable")}</option>{data.deliverables.map((deliverable) => <option key={deliverable.id} value={deliverable.id}>{deliverable.name}</option>)}</select></label>
          <label className="wide-field">{t("workItem.description")}<textarea rows={3} value={draft.description || ""} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
          <label className="wide-field">{t("agile.blockedReason")}<input value={draft.blocked_reason || ""} onChange={(event) => setDraft({ ...draft, blocked_reason: event.target.value })} /></label>
          <div className="form-actions"><button className="icon-button" onClick={() => setShowForm(false)} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy} type="submit">{busy ? t("common.saving") : t("common.create")}</button></div>
        </form>
      ) : null}

      <div className="scrum-overview agile-overview">
        <article className="scrum-metric"><b>{visibleItems.length}</b><span>{t("agile.totalItems")}</span></article>
        <article className="scrum-metric"><b>{wipCount}</b><span>{t("agile.wip")}</span></article>
        <article className="scrum-metric"><b>{blockedCount}</b><span>{t("agile.blocked")}</span></article>
        <article className="scrum-metric"><b>{throughput}</b><span>{t("agile.throughput")}</span></article>
        <article className="burndown-card">
          <div><b>{mode === "Kanban" ? t("agile.flowSignal") : "Burndown"}</b><span>{t("scrum.sprintPercent", { percent: cyclePercent })}</span></div>
          <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label="Agile progress chart">
            <polyline className="burndown-ideal" points={chart.ideal} />
            <polyline className="burndown-actual" points={chart.actual} />
          </svg>
        </article>
      </div>

      {activeTab === "settings" ? (
        <div className="agile-settings-grid">
          <form className="kanban-status-form" onSubmit={createStatus}>
            <input aria-label={t("agile.newStatus")} placeholder={t("agile.newStatus")} value={newStatus} onChange={(event) => setNewStatus(event.target.value)} />
            <button className="inline-action" disabled={busy || !newStatus.trim()} type="submit">{t("agile.createStatus")}</button>
          </form>
          <div className="panel compact-panel">
            <h2>{t("agile.mode")}</h2>
            <p className="muted-copy">{t(`agile.modeHelp.${mode}`)}</p>
          </div>
        </div>
      ) : null}

      {activeTab === "metrics" ? (
        <div className="agile-metrics-grid">
          <article className="panel compact-panel"><h2>{t("agile.cycle")}</h2><p className="muted-copy">{activeCycle ? `${activeCycle.name}: ${activeCycle.goal || activeCycle.status}` : t("agile.noCycle")}</p></article>
          <article className="panel compact-panel"><h2>{t("agile.flow")}</h2><p className="muted-copy">{t("agile.flowSummary", { wip: wipCount, blocked: blockedCount, done: throughput })}</p></article>
          <article className="panel compact-panel"><h2>{t("agile.planConnection")}</h2><p className="muted-copy">{t("agile.planLinked", { count: visibleItems.filter((item) => item.master_task_id).length })}</p></article>
        </div>
      ) : null}

      {activeTab === "list" ? (
        <div className="table-scroll">
          <table className="data-table agile-list-table">
            <thead><tr><th>{t("workItem.title")}</th><th>{t("workItem.type")}</th><th>{t("common.status")}</th><th>{t("common.owner")}</th><th>{t("agile.cycle")}</th><th>Plan Maestro</th><th>{t("story.points")}</th></tr></thead>
            <tbody>
              {visibleItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.title}</td>
                  <td><span className="badge neutral">{item.work_type || "Historia"}</span></td>
                  <td>{item.status}</td>
                  <td>{item.assignee || t("knowledge.noOwner")}</td>
                  <td>{data.sprints.find((cycle) => cycle.id === item.sprint_id)?.name || t("agile.noCycle")}</td>
                  <td>{item.master_task_id ? taskLabels.get(item.master_task_id) : t("agile.noMasterPlanLink")}</td>
                  <td>{item.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {activeTab === "board" ? (
        <>
          {mode === "Scrum" && data.sprints.length ? (
            <div className="agile-cycle-filter">
              <label>{t("agile.activeCycle")}<select value={selectedCycleId} onChange={(event) => setSelectedCycleId(event.target.value === "all" ? "all" : Number(event.target.value))}><option value="all">{t("agile.autoCycle")}</option>{data.sprints.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name} - {cycle.status}</option>)}</select></label>
            </div>
          ) : null}
          <div className="board agile-board">
            {statuses.map((status) => (
              <article
                className={`board-column${dragOverStatus === status ? " drop-target" : ""}${draggingStatus === status ? " dragging-column" : ""}`}
                key={status}
                onDragLeave={() => setDragOverStatus("")}
                onDragOver={(event) => {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                  setDragOverStatus(status);
                }}
                onDrop={(event) => void onDropItem(event, status)}
              >
                <h2
                  className="board-column-handle"
                  draggable={canWrite && !busy}
                  onDragEnd={() => {
                    setDraggingStatus("");
                    setDragOverStatus("");
                  }}
                  onDragStart={(event) => onColumnDragStart(event, status)}
                >
                  <span>{status}</span><small>{visibleItems.filter((item) => item.status === status).length}</small>
                </h2>
                {visibleItems.filter((item) => item.status === status).map(renderCard)}
                {!visibleItems.some((item) => item.status === status) ? <p className="muted-copy">{t("agile.noItems")}</p> : null}
              </article>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
