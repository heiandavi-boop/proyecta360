import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { DependencyIn, StoryIn, TaskIn, TaskUpdate } from "@contracts/types";

import type { BootstrapPayload, Story, Task } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type MasterPlanViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  onCreateTask: (task: TaskIn) => Promise<void>;
  onDeleteTask: (taskId: number) => Promise<void>;
  onCreateDependency: (dependency: DependencyIn) => Promise<void>;
  onIndentTask: (taskId: number) => Promise<void>;
  onOutdentTask: (taskId: number) => Promise<void>;
  onToggleTask: (taskId: number) => Promise<void>;
  onUpdateTask: (taskId: number, task: TaskUpdate) => Promise<void>;
  onCreateStory: (story: StoryIn) => Promise<void>;
  onUpdateStory: (story: Story) => Promise<void>;
  canWrite?: boolean;
};

type GanttTask = Task & {
  duration_days?: number;
  is_expanded?: number;
  outline_level?: number;
  order_index?: number;
  predecessor_id?: number | null;
  is_critical_path?: boolean;
};

const dayMs = 86400000;
const monthLabels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

function dateMs(value?: string): number {
  const time = new Date(`${value || ""}T00:00:00`).getTime();
  return Number.isFinite(time) ? time : Date.now();
}

function isoDate(time: number): string {
  return new Date(time).toISOString().slice(0, 10);
}

function shortDate(time: number): string {
  const date = new Date(time);
  return `${String(date.getUTCDate()).padStart(2, "0")}/${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

function daySpan(start: number, end: number): number {
  return Math.max(1, Math.round((end - start) / dayMs) + 1);
}

function ganttGeometry(tasks: GanttTask[]) {
  const starts = tasks.map((task) => dateMs(task.start_date));
  const ends = tasks.map((task) => dateMs(task.end_date || task.start_date));
  const minTask = Math.min(...starts, Date.now());
  const maxTask = Math.max(...ends, minTask + dayMs);
  const minDate = new Date(minTask);
  const maxDate = new Date(maxTask);
  const min = Date.UTC(minDate.getUTCFullYear(), minDate.getUTCMonth(), 1);
  const max = Date.UTC(maxDate.getUTCFullYear(), maxDate.getUTCMonth() + 1, 1);
  const total = Math.max(dayMs, max - min);
  const months: Array<{ label: string; left: number; width: number }> = [];
  let cursor = new Date(min);
  while (cursor.getTime() < max) {
    const monthStart = cursor.getTime();
    const next = Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 1, 1);
    months.push({
      label: `${monthLabels[cursor.getUTCMonth()]} '${String(cursor.getUTCFullYear()).slice(2)}`,
      left: ((monthStart - min) / total) * 100,
      width: ((next - monthStart) / total) * 100,
    });
    cursor = new Date(next);
  }
  const tickCount = Math.min(18, Math.max(10, Math.ceil(total / (dayMs * 30))));
  const ticks = Array.from({ length: tickCount }, (_, index) => {
    const time = min + (total / tickCount) * index;
    return { label: shortDate(time), left: (index / tickCount) * 100 };
  });
  return { min, max, total, months, ticks };
}

function taskLeft(task: GanttTask, timeline: ReturnType<typeof ganttGeometry>) {
  return Math.max(1.2, Math.min(98, ((dateMs(task.start_date) - timeline.min) / timeline.total) * 100));
}

function taskWidth(task: GanttTask, timeline: ReturnType<typeof ganttGeometry>) {
  const start = dateMs(task.start_date);
  const end = dateMs(task.end_date || task.start_date);
  if (task.task_type === "milestone") return 0;
  return Math.max(3.2, ((end - start + dayMs) / timeline.total) * 100);
}

function isLate(task: GanttTask) {
  return dateMs(task.end_date || task.start_date) < Date.now() && Number(task.progress || 0) < 100;
}

function isCritical(task: GanttTask) {
  const status = String(task.status || "").toLowerCase();
  return Boolean(task.is_critical_path) || status.includes("crit") || status.includes("riesgo");
}

function taskVisualClass(task: GanttTask) {
  const classes = [];
  if (task.task_type === "summary") classes.push("summary-row");
  if (task.task_type === "milestone") classes.push("milestone-row");
  if (isLate(task)) classes.push("late-row");
  if (isCritical(task)) classes.push("critical-row");
  return classes.join(" ");
}

function barClass(task: GanttTask) {
  if (task.task_type === "summary") return "is-summary";
  if (task.task_type === "milestone") return "is-milestone";
  if (Number(task.progress || 0) >= 100) return "is-done";
  if (isCritical(task)) return "is-critical";
  if (isLate(task)) return "is-late";
  return "is-active";
}

function wbsCodes(tasks: GanttTask[]) {
  const counters: number[] = [];
  return tasks.map((task) => {
    const level = Math.max(0, Number(task.outline_level || (task.parent_id ? 1 : 0)));
    if (level > 0 && !counters[0]) counters[0] = 1;
    counters[level] = (counters[level] || 0) + 1;
    counters.length = level + 1;
    return counters.join(".");
  });
}

function dependencyGeometry(previous: GanttTask, current: GanttTask, timeline: ReturnType<typeof ganttGeometry>) {
  const previousRight = taskLeft(previous, timeline) + taskWidth(previous, timeline);
  const currentLeft = taskLeft(current, timeline);
  if (currentLeft <= previousRight + 0.6) return null;
  return { left: previousRight, width: currentLeft - previousRight };
}

function uniquePeople(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean))).sort((left, right) => left.localeCompare(right));
}

function childCounts(tasks: GanttTask[]) {
  return tasks.reduce<Record<number, number>>((counts, task) => {
    if (task.parent_id) counts[task.parent_id] = (counts[task.parent_id] || 0) + 1;
    return counts;
  }, {});
}

function visibleTasks(tasks: GanttTask[]) {
  const byId = new Map(tasks.map((task) => [task.id, task]));
  return tasks.filter((task) => {
    let parentId = task.parent_id;
    while (parentId) {
      const parent = byId.get(parentId);
      if (!parent) return true;
      if (Number(parent.is_expanded ?? 1) === 0) return false;
      parentId = parent.parent_id || null;
    }
    return true;
  });
}

function doneStory(story: Story) {
  return ["hecho", "done", "completado", "cerrado"].includes(String(story.status || "").toLowerCase());
}

function scrumProgress(stories: Story[]) {
  const totalPoints = stories.reduce((sum, story) => sum + Number(story.points || 0), 0);
  const donePoints = stories.filter(doneStory).reduce((sum, story) => sum + Number(story.points || 0), 0);
  if (totalPoints > 0) return Math.round((donePoints / totalPoints) * 100);
  return stories.length ? Math.round((stories.filter(doneStory).length / stories.length) * 100) : 0;
}

export function MasterPlanView({ busy = false, canWrite = true, data, onCreateTask, onCreateDependency, onDeleteTask, onIndentTask, onOutdentTask, onToggleTask, onUpdateTask, onCreateStory, onUpdateStory }: MasterPlanViewProps) {
  const { t } = useI18n();
  const tasks = data.tasks as GanttTask[];
  const [showForm, setShowForm] = useState(false);
  const [expandedTimeline, setExpandedTimeline] = useState(false);
  const [linkMode, setLinkMode] = useState(false);
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const [linkSourceId, setLinkSourceId] = useState<number | null>(null);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [scrumPanelTaskId, setScrumPanelTaskId] = useState<number | null>(null);
  const [scrumPanelMode, setScrumPanelMode] = useState<"view" | "link">("view");
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [storyDraft, setStoryDraft] = useState<StoryIn>({
    project_id: data.current_project.id,
    title: "",
    status: "Por hacer",
    points: 1,
    assignee: "",
    priority: "Media",
    master_task_id: null,
  });
  const [draft, setDraft] = useState<TaskIn>({
    project_id: data.current_project.id,
    title: "",
    start_date: data.current_project.start_date,
    duration_days: 1,
    owner: "",
    progress: 0,
    status: "Pendiente",
    task_type: "task",
  });

  const visible = useMemo(() => {
    const expandedTasks = visibleTasks(tasks);
    return showCriticalOnly ? expandedTasks.filter(isCritical) : expandedTasks;
  }, [showCriticalOnly, tasks]);
  const childrenByTask = useMemo(() => childCounts(tasks), [tasks]);
  const timeline = useMemo(() => ganttGeometry(visible), [visible]);
  const wbs = useMemo(() => wbsCodes(visible), [visible]);
  const allWbs = useMemo(() => wbsCodes(tasks), [tasks]);
  const ownerOptions = useMemo(() => uniquePeople([
    data.current_project.project_manager,
    ...data.resources.map((resource) => resource.name),
    ...data.tasks.map((task) => task.owner),
    ...data.risks.map((risk) => risk.owner),
    ...data.components.map((component) => component.owner),
    ...data.deliverables.map((deliverable) => deliverable.owner),
    ...data.stories.map((story) => story.assignee),
  ]), [data.components, data.current_project.project_manager, data.deliverables, data.resources, data.risks, data.stories, data.tasks]);
  const milestones = tasks.filter((task) => task.task_type === "milestone").slice(0, 5);
  const criticalTasks = tasks.filter(isCritical);
  const storiesByTask = useMemo(() => data.stories.reduce<Record<number, Story[]>>((groups, story) => {
    if (story.master_task_id) groups[story.master_task_id] = [...(groups[story.master_task_id] || []), story];
    return groups;
  }, {}), [data.stories]);
  const sprintById = useMemo(() => new Map(data.sprints.map((sprint) => [sprint.id, sprint])), [data.sprints]);
  const selectedScrumTask = scrumPanelTaskId ? tasks.find((task) => task.id === scrumPanelTaskId) || null : null;
  const selectedScrumStories = selectedScrumTask ? storiesByTask[selectedScrumTask.id] || [] : [];
  const unlinkedStories = data.stories.filter((story) => !story.master_task_id);
  const selectedScrumProgress = scrumProgress(selectedScrumStories);
  const timelineWidth = Math.max(expandedTimeline ? 1600 : 980, timeline.months.length * (expandedTimeline ? 110 : 82));
  const todayLeft = Math.max(0, Math.min(100, ((Date.now() - timeline.min) / timeline.total) * 100));
  const projectStart = tasks.length ? isoDate(Math.min(...tasks.map((task) => dateMs(task.start_date)))) : data.current_project.start_date;
  const projectEnd = tasks.length ? isoDate(Math.max(...tasks.map((task) => dateMs(task.end_date || task.start_date)))) : data.current_project.end_date;
  const totalDuration = tasks.length ? daySpan(dateMs(projectStart), dateMs(projectEnd)) : 0;

  useEffect(() => {
    setDraft((current) => ({ ...current, project_id: data.current_project.id, start_date: current.title ? current.start_date : data.current_project.start_date }));
  }, [data.current_project.id, data.current_project.start_date]);

  useEffect(() => {
    setStoryDraft((current) => ({ ...current, project_id: data.current_project.id }));
  }, [data.current_project.id]);

  useEffect(() => {
    function closeOpenMenu() {
      setOpenMenuId(null);
    }
    if (openMenuId === null) return undefined;
    window.addEventListener("click", closeOpenMenu);
    return () => window.removeEventListener("click", closeOpenMenu);
  }, [openMenuId]);

  async function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateTask({ ...draft, project_id: data.current_project.id });
    setShowForm(false);
    setDraft((current) => ({ ...current, title: "", duration_days: 1, progress: 0 }));
  }

  function openTaskForm(taskType: "task" | "milestone") {
    setDraft((current) => ({ ...current, task_type: taskType, duration_days: taskType === "milestone" ? 0 : current.duration_days || 1, owner: current.owner || ownerOptions[0] || "" }));
    setShowForm(true);
  }

  async function selectTaskForDependency(task: GanttTask) {
    if (!canWrite || !linkMode || busy) return;
    if (!linkSourceId) {
      setLinkSourceId(task.id);
      return;
    }
    if (linkSourceId === task.id) {
      setLinkSourceId(null);
      return;
    }
    await onCreateDependency({
      project_id: data.current_project.id,
      predecessor_id: linkSourceId,
      successor_id: task.id,
      dependency_type: "FS",
      lag_days: 0,
    });
    setLinkMode(false);
    setLinkSourceId(null);
  }

  function openChildTaskForm(task: GanttTask, index: number, asChild: boolean) {
    const level = Math.max(0, Number(task.outline_level || (task.parent_id ? 1 : 0)));
    setDraft({
      project_id: data.current_project.id,
      title: "",
      start_date: task.start_date || data.current_project.start_date,
      duration_days: 1,
      owner: task.owner || ownerOptions[0] || "",
      progress: 0,
      status: "Pendiente",
      task_type: "task",
      parent_id: asChild ? task.id : task.parent_id || null,
      outline_level: asChild ? Math.min(5, level + 1) : level,
      order_index: Number(task.order_index || index + 1) + 1,
    });
    setShowForm(true);
  }

  async function recalculateSchedule() {
    const firstTask = tasks[0];
    if (!firstTask || busy) return;
    await onUpdateTask(firstTask.id, { duration_days: firstTask.duration_days ?? daySpan(dateMs(firstTask.start_date), dateMs(firstTask.end_date || firstTask.start_date)) });
  }

  function selectRow(task: GanttTask) {
    setSelectedTaskId(task.id);
    void selectTaskForDependency(task);
  }

  async function runMenuAction(action: "indent" | "outdent" | "subtask" | "below" | "milestone" | "toggle" | "edit" | "delete" | "scrum" | "linkScrum" | "syncScrum", task: GanttTask, index: number) {
    setOpenMenuId(null);
    const level = Math.max(0, Number(task.outline_level || (task.parent_id ? 1 : 0)));
    if (action === "indent") await onIndentTask(task.id);
    if (action === "outdent") await onOutdentTask(task.id);
    if (action === "toggle") await onToggleTask(task.id);
    if (action === "subtask") openChildTaskForm(task, index, true);
    if (action === "below") openChildTaskForm(task, index, false);
    if (action === "milestone") await onUpdateTask(task.id, { task_type: "milestone", duration_days: 0 });
    if (action === "edit") {
      setEditingTitleId(task.id);
      setEditingTitle(task.title);
    }
    if (action === "scrum" || action === "linkScrum") {
      setScrumPanelTaskId(task.id);
      setScrumPanelMode(action === "linkScrum" ? "link" : "view");
      setStoryDraft((current) => ({ ...current, master_task_id: task.id, assignee: current.assignee || task.owner || "" }));
    }
    if (action === "syncScrum") await syncTaskFromScrum(task);
    if (action === "delete" && window.confirm(t("task.deleteConfirm"))) await onDeleteTask(task.id);
  }

  async function saveTitle(task: GanttTask) {
    const title = editingTitle.trim();
    setEditingTitleId(null);
    if (title && title !== task.title) await onUpdateTask(task.id, { title });
  }

  async function createLinkedStory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedScrumTask) return;
    await onCreateStory({ ...storyDraft, project_id: data.current_project.id, master_task_id: selectedScrumTask.id });
    setStoryDraft((current) => ({ ...current, title: "", points: 1, master_task_id: selectedScrumTask.id }));
  }

  async function syncTaskFromScrum(task: GanttTask) {
    const progress = scrumProgress(storiesByTask[task.id] || []);
    if (!window.confirm(`Avance actual Plan Maestro: ${task.progress}%\nAvance Scrum sugerido: ${progress}%\nDiferencia: ${progress - Number(task.progress || 0)} puntos\n\n¿Deseas actualizar el avance de la tarea?`)) return;
    await onUpdateTask(task.id, { progress });
  }

  return (
    <section className="master-gantt-layout full-span">
      <div className="gantt-workspace">
        <div className="gantt-titlebar">
          <div>
            <h2>{t("gantt.title")}</h2>
            <span>{t("gantt.summary", { total: tasks.length, summaries: tasks.filter((task) => task.task_type === "summary").length, tasks: tasks.filter((task) => task.task_type !== "milestone").length, milestones: tasks.filter((task) => task.task_type === "milestone").length })}</span>
          </div>
          <div className="gantt-toolbar">
            {canWrite ? <button className="primary-action compact-action" disabled={busy} onClick={() => openTaskForm("task")} type="button">+ {t("gantt.addTask").replace("+", "").trim()}</button> : null}
            {canWrite ? <button className="inline-action" disabled={busy} onClick={() => openTaskForm("milestone")} type="button">+ {t("gantt.addMilestone").replace("+", "").trim()}</button> : null}
            {canWrite ? <button className={`inline-action${linkMode ? " active-tool" : ""}`} disabled={busy} onClick={() => { setLinkMode((value) => !value); setLinkSourceId(null); }} type="button">{t("gantt.link")}</button> : null}
            <button className={`inline-action${expandedTimeline ? " active-tool" : ""}`} disabled={busy} onClick={() => setExpandedTimeline((value) => !value)} type="button">{expandedTimeline ? t("gantt.collapse") : t("gantt.expand")}</button>
            <button className={`inline-action${showCriticalOnly ? " active-tool" : ""}`} disabled={!criticalTasks.length} onClick={() => setShowCriticalOnly((value) => !value)} type="button">{showCriticalOnly ? "Ver todas" : "Ver ruta crítica"}</button>
            {canWrite ? <button className="inline-action" disabled={busy || !tasks.length} onClick={() => void recalculateSchedule()} type="button">{t("gantt.recalculate")}</button> : null}
          </div>
        </div>

        {linkMode ? (
          <div className="gantt-mode-banner">{linkSourceId ? "Selecciona la tarea sucesora para crear la dependencia." : "Selecciona la tarea predecesora."}</div>
        ) : null}

        {canWrite && showForm ? (
          <form className="inline-form" onSubmit={(event) => void submitTask(event)}>
            <label className="wide-field">{t("gantt.taskName")}<input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
            <label>{t("gantt.start")}<input required type="date" value={draft.start_date} onChange={(event) => setDraft({ ...draft, start_date: event.target.value })} /></label>
            <label>{t("gantt.duration")}<input min="0" type="number" value={draft.duration_days || 0} onChange={(event) => setDraft({ ...draft, duration_days: Number(event.target.value) })} /></label>
            <label>{t("gantt.owner")}<select value={draft.owner || ""} onChange={(event) => setDraft({ ...draft, owner: event.target.value })}><option value="">{t("knowledge.noOwner")}</option>{ownerOptions.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select></label>
            <label>{t("gantt.progress")}<input max="100" min="0" type="number" value={draft.progress || 0} onChange={(event) => setDraft({ ...draft, progress: Number(event.target.value) })} /></label>
            <label>{t("common.type")}<select value={draft.task_type || "task"} onChange={(event) => setDraft({ ...draft, task_type: event.target.value })}><option value="task">{t("task.task")}</option><option value="milestone">{t("task.milestone")}</option></select></label>
            <div className="form-actions">
              <button className="icon-button" onClick={() => setShowForm(false)} type="button">{t("common.cancel")}</button>
              <button className="primary-action" disabled={busy} type="submit">{busy ? t("common.saving") : t("task.createAction")}</button>
            </div>
          </form>
        ) : null}

        <div className="gantt-split gantt-shell">
          <div className="gantt-table-pane">
            <div className="gantt-table-head">
              <b>#</b><b>{t("gantt.taskName")}</b><b>{t("gantt.duration")}</b><b>{t("gantt.start")}</b><b>{t("gantt.end")}</b><b>{t("gantt.predecessors")}</b><b>{t("gantt.owner")}</b><b>%</b><b></b>
            </div>
            <div className="gantt-table-body">
              {visible.map((task, index) => {
                const start = dateMs(task.start_date);
                const end = dateMs(task.end_date || task.start_date);
                const outline = Math.max(0, Number(task.outline_level || (task.parent_id ? 1 : 0)));
                const predecessor = task.predecessor_id || (index > 0 ? wbs[index - 1] : "-");
                const hasChildren = Boolean(childrenByTask[task.id]);
                const isExpanded = Number(task.is_expanded ?? 1) === 1;
                const openMenuUp = index >= visible.length - 4;
                return (
                  <div className={`gantt-table-row ${taskVisualClass(task)}${linkMode ? " linkable-row" : ""}${linkSourceId === task.id ? " link-source-row" : ""}${selectedTaskId === task.id ? " selected-row" : ""}`} key={task.id} onClick={() => selectRow(task)}>
                    <span className="wbs-code">{wbs[index]}</span>
                    <span className="gantt-task-title" style={{ paddingLeft: `${outline * 18 + 8}px` }} title={task.title}>
                      {canWrite && hasChildren ? <button className="row-caret" disabled={busy} onClick={(event) => { event.stopPropagation(); void runMenuAction("toggle", task, index); }} title={isExpanded ? "Contraer" : "Expandir"} type="button">{isExpanded ? "v" : ">"}</button> : null}
                      {task.task_type === "summary" && !hasChildren ? <i className="summary-glyph">v</i> : null}
                      {task.task_type === "milestone" ? <i className="milestone-glyph" /> : null}
                      {editingTitleId === task.id ? (
                        <input
                          autoFocus
                          className="task-title-editor"
                          value={editingTitle}
                          onBlur={() => void saveTitle(task)}
                          onChange={(event) => setEditingTitle(event.target.value)}
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") void saveTitle(task);
                            if (event.key === "Escape") setEditingTitleId(null);
                          }}
                        />
                      ) : (
                        <b onDoubleClick={(event) => { event.stopPropagation(); if (canWrite) { setEditingTitleId(task.id); setEditingTitle(task.title); } }}>{task.title}</b>
                      )}
                      {storiesByTask[task.id]?.length ? <small className="scrum-link-badge" title={`Avance Scrum ${scrumProgress(storiesByTask[task.id])}%`}>Scrum: {storiesByTask[task.id].length} HU</small> : null}
                      {isCritical(task) ? <small className="critical-path-badge" title="Esta tarea pertenece a la ruta critica porque impacta la fecha final del proyecto.">Crítica</small> : null}
                    </span>
                    <span>{daySpan(start, end)} {t("gantt.daysUnit")}</span>
                    <span>{task.start_date}</span>
                    <span>{task.end_date || task.start_date}</span>
                    <span title={String(predecessor)}>{predecessor}</span>
                    <span title={task.owner || "PMO"}>{task.owner || "PMO"}</span>
                    <span className="gantt-progress-cell"><input className="grid-control" defaultValue={task.progress} disabled={busy || !canWrite} max="100" min="0" onBlur={(event) => canWrite ? void onUpdateTask(task.id, { progress: Number(event.target.value) }) : undefined} type="number" /><b>{task.progress}%</b></span>
                    <span className="row-context">
                      {(canWrite || storiesByTask[task.id]?.length) ? <button className="row-menu-trigger" disabled={busy} onClick={(event) => { event.stopPropagation(); setSelectedTaskId(task.id); setOpenMenuId((current) => current === task.id ? null : task.id); }} title="Mas opciones" type="button">...</button> : null}
                      {openMenuId === task.id ? (
                        <span className={`row-menu${openMenuUp ? " open-up" : ""}`} onClick={(event) => event.stopPropagation()}>
                          {canWrite ? <button disabled={busy || index === 0 || outline >= 5} onClick={() => void runMenuAction("indent", task, index)} type="button">Indentar</button> : null}
                          {canWrite ? <button disabled={busy || (!task.parent_id && outline === 0)} onClick={() => void runMenuAction("outdent", task, index)} type="button">Desindentar</button> : null}
                          {canWrite ? <button disabled={busy || outline >= 5} onClick={() => void runMenuAction("subtask", task, index)} type="button">Agregar subtarea</button> : null}
                          {canWrite ? <button disabled={busy} onClick={() => void runMenuAction("below", task, index)} type="button">Agregar tarea debajo</button> : null}
                          {canWrite ? <button disabled={busy} onClick={() => void runMenuAction("edit", task, index)} type="button">Editar nombre</button> : null}
                          {canWrite ? <button disabled={busy || task.task_type === "milestone"} onClick={() => void runMenuAction("milestone", task, index)} type="button">Convertir en hito</button> : null}
                          {canWrite ? <button disabled={busy || !hasChildren} onClick={() => void runMenuAction("toggle", task, index)} type="button">{isExpanded ? "Contraer" : "Expandir"}</button> : null}
                          <button disabled={busy || !storiesByTask[task.id]?.length} onClick={() => void runMenuAction("scrum", task, index)} type="button">Ver Scrum asociado</button>
                          {canWrite ? <button disabled={busy} onClick={() => void runMenuAction("linkScrum", task, index)} type="button">Vincular con Scrum</button> : null}
                          {canWrite ? <button disabled={busy || !storiesByTask[task.id]?.length} onClick={() => void runMenuAction("syncScrum", task, index)} type="button">Sincronizar avance desde Scrum</button> : null}
                          {canWrite ? <button className="danger-menu-item" disabled={busy} onClick={() => void runMenuAction("delete", task, index)} type="button">Eliminar</button> : null}
                        </span>
                      ) : null}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="gantt-timeline-pane">
            <div className="gantt-timeline-scroll">
              <div className={`gantt-timeline-canvas${expandedTimeline ? " expanded-timeline" : ""}`} style={{ width: `${timelineWidth}px` }}>
                <div className="gantt-calendar-head">
                  <div className="gantt-months">{timeline.months.map((month) => <span key={month.label} style={{ left: `${month.left}%`, width: `${month.width}%` }}>{month.label}</span>)}</div>
                  <div className="gantt-ticks">{timeline.ticks.map((tick) => <span key={`${tick.label}-${tick.left}`} style={{ left: `${tick.left}%` }}>{tick.label}</span>)}</div>
                </div>
                <div className="gantt-timeline-body">
                  <div className="today-line" style={{ left: `${todayLeft}%` }}><small>{t("common.today")}</small></div>
                  {visible.map((task, index) => {
                    const dependency = index > 0 ? dependencyGeometry(visible[index - 1], task, timeline) : null;
                    return (
                      <div className={`gantt-timeline-row ${taskVisualClass(task)}${linkMode ? " linkable-row" : ""}${linkSourceId === task.id ? " link-source-row" : ""}${selectedTaskId === task.id ? " selected-row" : ""}`} key={task.id} onClick={() => selectRow(task)}>
                        {dependency ? <i className="dependency-line" style={{ left: `${dependency.left}%`, width: `${dependency.width}%` }} /> : null}
                        <i className={`gantt-bar ${barClass(task)}`} title={isCritical(task) ? "Esta tarea pertenece a la ruta critica porque impacta la fecha final del proyecto." : task.title} style={{ left: `${taskLeft(task, timeline)}%`, width: `${task.task_type === "milestone" ? undefined : `${taskWidth(task, timeline)}%`}` }}>
                          <em style={{ width: `${Math.max(0, Math.min(100, task.progress))}%` }} />
                        </i>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <aside className="gantt-inspector">
        <section>
          <h3>{t("gantt.keyMilestones")}</h3>
          {milestones.map((task) => <p key={task.id}><i>M</i><span title={task.title}>{task.title}</span><b>{task.end_date || task.start_date}</b></p>)}
          {!milestones.length ? <p className="muted-copy">{t("scrum.noStories")}</p> : null}
        </section>
        <section>
          <h3>{t("gantt.criticalDependencies")}</h3>
          {criticalTasks.slice(0, 9).map((task) => {
            const taskIndex = tasks.findIndex((item) => item.id === task.id);
            return <p key={task.id}><i>!</i><span>{allWbs[taskIndex] || taskIndex + 1} {task.title}</span><b>{task.end_date || task.start_date}</b></p>;
          })}
          {!criticalTasks.length ? <p className="muted-copy">{t("common.noData")}</p> : null}
        </section>
        <section>
          <h3>{t("gantt.planSummary")}</h3>
          <dl>
            <dt>{t("gantt.totalTasks")}</dt><dd>{tasks.length}</dd>
            <dt>{t("gantt.milestones")}</dt><dd>{milestones.length}</dd>
            <dt>{t("gantt.planDuration")}</dt><dd>{totalDuration} {t("gantt.daysUnit")}</dd>
            <dt>{t("gantt.planStart")}</dt><dd>{projectStart}</dd>
            <dt>{t("gantt.planEnd")}</dt><dd>{projectEnd}</dd>
          </dl>
        </section>
      </aside>
      {selectedScrumTask ? (
        <div className="modal-backdrop" onClick={() => setScrumPanelTaskId(null)}>
          <section className="scrum-link-panel" onClick={(event) => event.stopPropagation()}>
            <div className="panel-heading">
              <div>
                <h2>{scrumPanelMode === "link" ? "Vincular con Scrum" : "Scrum asociado"}</h2>
                <span>{selectedScrumTask.title}</span>
              </div>
              <button className="icon-button" onClick={() => setScrumPanelTaskId(null)} type="button">x</button>
            </div>
            <div className="scrum-sync-summary">
              <article><b>{selectedScrumStories.length}</b><span>Historias</span></article>
              <article><b>{selectedScrumStories.filter(doneStory).length}/{selectedScrumStories.length}</b><span>Completadas</span></article>
              <article><b>{selectedScrumProgress}%</b><span>Avance Scrum</span></article>
              <article><b>{selectedScrumTask.progress}%</b><span>Plan Maestro</span></article>
            </div>
            <div className="form-actions">
              {canWrite ? <button className="inline-action" disabled={busy || !selectedScrumStories.length} onClick={() => void syncTaskFromScrum(selectedScrumTask)} type="button">Sincronizar avance desde Scrum</button> : null}
              {canWrite ? <button className="inline-action" onClick={() => setScrumPanelMode(scrumPanelMode === "link" ? "view" : "link")} type="button">{scrumPanelMode === "link" ? "Ver historias" : "Vincular historias"}</button> : null}
            </div>
            {canWrite && scrumPanelMode === "link" ? (
              <>
                <form className="inline-form scrum-link-form" onSubmit={(event) => void createLinkedStory(event)}>
                  <label className="wide-field">Nueva historia<input required value={storyDraft.title} onChange={(event) => setStoryDraft({ ...storyDraft, title: event.target.value })} /></label>
                  <label>Puntos<input min="0" type="number" value={storyDraft.points || 0} onChange={(event) => setStoryDraft({ ...storyDraft, points: Number(event.target.value) })} /></label>
                  <label>Responsable<select value={storyDraft.assignee || ""} onChange={(event) => setStoryDraft({ ...storyDraft, assignee: event.target.value })}><option value="">Sin responsable</option>{ownerOptions.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select></label>
                  <label>Sprint<select value={storyDraft.sprint_id || ""} onChange={(event) => setStoryDraft({ ...storyDraft, sprint_id: event.target.value ? Number(event.target.value) : null })}><option value="">Sin sprint</option>{data.sprints.map((sprint) => <option key={sprint.id} value={sprint.id}>{sprint.name}</option>)}</select></label>
                  <div className="form-actions"><button className="primary-action" disabled={busy} type="submit">Crear historia vinculada</button></div>
                </form>
                <div className="linked-story-list">
                  <h3>Historias sin vínculo</h3>
                  {unlinkedStories.map((story) => <p key={story.id}><span>{story.title}</span><b>{story.points} pts</b><button className="inline-action" disabled={busy} onClick={() => void onUpdateStory({ ...story, master_task_id: selectedScrumTask.id })} type="button">Vincular</button></p>)}
                  {!unlinkedStories.length ? <p className="muted-copy">No hay historias sin vínculo.</p> : null}
                </div>
              </>
            ) : (
              <div className="linked-story-list">
                {selectedScrumStories.map((story) => {
                  const sprint = story.sprint_id ? sprintById.get(story.sprint_id) : null;
                  return <p key={story.id}><span>{story.title}<small>{sprint?.name || "Sin sprint"} - {story.status} - {story.assignee || "Sin responsable"}</small></span><b>{story.points} pts</b></p>;
                })}
                {!selectedScrumStories.length ? <p className="muted-copy">Esta tarea todavía no tiene historias Scrum asociadas.</p> : null}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </section>
  );
}
