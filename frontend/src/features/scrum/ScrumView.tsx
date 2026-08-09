import { useEffect, useMemo, useState, type DragEvent, type FormEvent } from "react";

import type { StoryIn } from "@contracts/types";

import type { BootstrapPayload, Story, Task } from "@/domain/project";
import { useI18n } from "@/i18n/i18n";

type ScrumViewProps = {
  data: BootstrapPayload;
  busy?: boolean;
  canWrite?: boolean;
  onCreateStory: (story: StoryIn) => Promise<void>;
  onUpdateStory: (story: Story) => Promise<void>;
};

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

export function ScrumView({ busy = false, canWrite = true, data, onCreateStory, onUpdateStory }: ScrumViewProps) {
  const { t } = useI18n();
  const statusStorageKey = `proyecta360.scrum.statuses.${data.current_project.id}`;
  const statusOrderStorageKey = `proyecta360.scrum.statusOrder.${data.current_project.id}`;
  const [customStatuses, setCustomStatuses] = useState<string[]>([]);
  const [statusOrder, setStatusOrder] = useState<string[]>([]);
  const [newStatus, setNewStatus] = useState("");
  const [draggingStoryId, setDraggingStoryId] = useState<number | null>(null);
  const [draggingStatus, setDraggingStatus] = useState("");
  const [dragOverStatus, setDragOverStatus] = useState("");
  const baseStatuses = useMemo(() => Array.from(new Set([
    "Por hacer",
    "En progreso",
    "Hecho",
    ...customStatuses,
    ...data.stories.map((story) => story.status || "Por hacer"),
  ].filter(Boolean))), [customStatuses, data.stories]);
  const statuses = useMemo(() => orderStatuses(baseStatuses, statusOrder), [baseStatuses, statusOrder]);
  const totalPoints = data.stories.reduce((sum, story) => sum + Number(story.points || 0), 0);
  const completedPoints = data.stories.filter((story) => story.status === "Hecho").reduce((sum, story) => sum + Number(story.points || 0), 0);
  const chart = useMemo(() => burndownPoints(totalPoints, completedPoints), [totalPoints, completedPoints]);
  const ownerOptions = useMemo(() => uniquePeople([
    data.current_project.project_manager,
    ...data.resources.map((resource) => resource.name),
    ...data.tasks.map((task) => task.owner),
    ...data.risks.map((risk) => risk.owner),
    ...data.components.map((component) => component.owner),
    ...data.deliverables.map((deliverable) => deliverable.owner),
    ...data.stories.map((story) => story.assignee),
  ]), [data.components, data.current_project.project_manager, data.deliverables, data.resources, data.risks, data.stories, data.tasks]);
  const sprintPercent = totalPoints ? Math.round((completedPoints / totalPoints) * 100) : 0;
  const taskCodes = useMemo(() => taskWbsCodes(data.tasks), [data.tasks]);
  const taskLabels = useMemo(() => new Map(data.tasks.map((task, index) => [
    task.id,
    `${taskCodes[index]} ${task.title}`,
  ])), [data.tasks, taskCodes]);
  const taskOptions = useMemo(() => data.tasks.map((task, index) => ({
    task,
    label: `${taskCodes[index]} ${task.title} - Fin: ${task.end_date || task.start_date} - ${task.status || "Pendiente"}`,
  })), [data.tasks, taskCodes]);
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<StoryIn>({
    project_id: data.current_project.id,
    title: "",
    status: "Por hacer",
    points: 1,
    assignee: "",
    priority: "Media",
    master_task_id: null,
  });

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(statusStorageKey);
      setCustomStatuses(stored ? JSON.parse(stored) as string[] : []);
      const storedOrder = window.localStorage.getItem(statusOrderStorageKey);
      setStatusOrder(storedOrder ? JSON.parse(storedOrder) as string[] : []);
    } catch {
      setCustomStatuses([]);
      setStatusOrder([]);
    }
  }, [statusOrderStorageKey, statusStorageKey]);

  function persistCustomStatuses(nextStatuses: string[]) {
    setCustomStatuses(nextStatuses);
    window.localStorage.setItem(statusStorageKey, JSON.stringify(nextStatuses));
  }

  function persistStatusOrder(nextOrder: string[]) {
    setStatusOrder(nextOrder);
    window.localStorage.setItem(statusOrderStorageKey, JSON.stringify(nextOrder));
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

  function onDragStart(event: DragEvent<HTMLElement>, storyId: number) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-proyecta360-story", String(storyId));
    setDraggingStoryId(storyId);
  }

  function onColumnDragStart(event: DragEvent<HTMLElement>, status: string) {
    event.stopPropagation();
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-proyecta360-column", status);
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

  async function onDropStory(event: DragEvent<HTMLElement>, status: string) {
    event.preventDefault();
    if (Array.from(event.dataTransfer.types).includes("application/x-proyecta360-column")) {
      onDropColumn(status);
      return;
    }
    setDragOverStatus("");
    const storyId = Number(event.dataTransfer.getData("application/x-proyecta360-story") || draggingStoryId);
    const story = data.stories.find((item) => item.id === storyId);
    setDraggingStoryId(null);
    if (!canWrite || !story || story.status === status || busy) return;
    await onUpdateStory({ ...story, status });
  }

  async function submitStory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateStory({ ...draft, project_id: data.current_project.id });
    setShowForm(false);
    setDraft((current) => ({ ...current, title: "", points: 1, master_task_id: null }));
  }

  return (
    <section className="panel full-span">
      <div className="panel-heading">
        <div>
          <h2>{t("scrum.title")}</h2>
          <span>{t("scrum.description")}</span>
        </div>
        {canWrite ? (
          <button className="primary-action compact-action" disabled={busy} onClick={() => setShowForm((value) => !value)} type="button">
            {t("story.new")}
          </button>
        ) : null}
      </div>
      {canWrite && showForm ? (
        <form className="inline-form" onSubmit={(event) => void submitStory(event)}>
          <label className="wide-field">{t("story.title")}<input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          <label className="wide-field">Actividad del Plan Maestro<select value={draft.master_task_id || ""} onChange={(event) => setDraft({ ...draft, master_task_id: event.target.value ? Number(event.target.value) : null })}><option value="">Sin vínculo</option>{taskOptions.map(({ task, label }) => <option key={task.id} value={task.id}>{label}</option>)}</select></label>
          <label>Sprint<select value={draft.sprint_id || ""} onChange={(event) => setDraft({ ...draft, sprint_id: event.target.value ? Number(event.target.value) : null })}><option value="">Sin sprint</option>{data.sprints.map((sprint) => <option key={sprint.id} value={sprint.id}>{sprint.name} - {sprint.status}</option>)}</select></label>
          <label>{t("common.status")}<select value={draft.status || "Por hacer"} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>{statuses.map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
          <label>{t("story.points")}<input min="0" type="number" value={draft.points || 0} onChange={(event) => setDraft({ ...draft, points: Number(event.target.value) })} /></label>
          <label>{t("common.owner")}<select value={draft.assignee || ""} onChange={(event) => setDraft({ ...draft, assignee: event.target.value })}><option value="">{t("knowledge.noOwner")}</option>{ownerOptions.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select></label>
          <label>{t("story.priority")}<select value={draft.priority || "Media"} onChange={(event) => setDraft({ ...draft, priority: event.target.value })}><option value="Alta">{t("story.high")}</option><option value="Media">{t("story.medium")}</option><option value="Baja">{t("story.low")}</option></select></label>
          <div className="form-actions"><button className="icon-button" onClick={() => setShowForm(false)} type="button">{t("common.cancel")}</button><button className="primary-action" disabled={busy} type="submit">{busy ? t("common.saving") : t("common.create")}</button></div>
        </form>
      ) : null}
      {canWrite ? <form className="kanban-status-form" onSubmit={createStatus}>
        <input aria-label="Nuevo estado Scrum" placeholder="Nuevo estado" value={newStatus} onChange={(event) => setNewStatus(event.target.value)} />
        <button className="inline-action" disabled={busy || !newStatus.trim()} type="submit">Crear estado</button>
      </form> : null}
      <div className="scrum-overview">
        <article className="scrum-metric"><b>{data.stories.length}</b><span>{t("scrum.totalStories")}</span></article>
        <article className="scrum-metric"><b>{data.stories.filter((story) => story.status === "En progreso").length}</b><span>{t("scrum.inProgress")}</span></article>
        <article className="scrum-metric"><b>{completedPoints}/{totalPoints}</b><span>{t("story.points")}</span></article>
        <article className="burndown-card">
          <div><b>Burndown</b><span>{t("scrum.sprintPercent", { percent: sprintPercent })}</span></div>
          <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label="Burndown chart">
            <polyline className="burndown-ideal" points={chart.ideal} />
            <polyline className="burndown-actual" points={chart.actual} />
          </svg>
        </article>
      </div>
      <div className="board">
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
            onDrop={(event) => void onDropStory(event, status)}
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
              <span>{status}</span><small>{data.stories.filter((story) => story.status === status).length}</small>
            </h2>
            {data.stories.filter((story) => story.status === status).map((story) => (
              <div
                className={`story-card${draggingStoryId === story.id ? " dragging" : ""}`}
                draggable={canWrite && !busy}
                key={story.id}
                onDragEnd={() => {
                  setDraggingStoryId(null);
                  setDragOverStatus("");
                }}
                onDragStart={(event) => onDragStart(event, story.id)}
              >
                <b>{story.title}</b>
                <span>{story.assignee || t("knowledge.noOwner")} - {story.priority}</span>
                {story.master_task_id ? <small className="story-plan-link">Plan Maestro: {taskLabels.get(story.master_task_id) || `Tarea ${story.master_task_id}`}</small> : null}
                <small>{story.points} {t("story.points")}</small>
              </div>
            ))}
            {!data.stories.some((story) => story.status === status) ? <p className="muted-copy">{t("scrum.noStories")}</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}
