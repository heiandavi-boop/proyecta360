// Gantt / Plan Maestro view: task table, timeline bars, dependency arrows,
// side panels (milestones + dependencies) and the task editor modal.
import { $, safe, clamp, parseDate, daysBetween, barClass, phaseClass } from '../dom.js';
import { state } from '../state.js';
import { openModal, closeModal, modalActions, getPhasesOptions, getTaskOptions, getResourceNamesOptions } from '../modal.js';
import * as api from '../api.js';
import { toast } from '../dom.js';
import { load } from '../main.js';

export function timelineBounds() {
  const p = state.current_project;
  let min = parseDate(p.start_date),
    max = parseDate(p.end_date);
  state.tasks.forEach((t) => {
    min = parseDate(t.start_date) < min ? parseDate(t.start_date) : min;
    max = parseDate(t.end_date) > max ? parseDate(t.end_date) : max;
  });
  min.setDate(min.getDate() - 3);
  max.setDate(max.getDate() + 7);
  return { min, max, total: Math.max(1, Math.round((max - min) / (1000 * 60 * 60 * 24))) };
}

function phaseColorDot(phase) {
  return `<i class="phase-dot ${phaseClass(phase)}"></i>`;
}

export function renderGantt() {
  const tasks = [...state.tasks].sort((a, b) => (a.order_index || 0) - (b.order_index || 0) || a.id - b.id);
  $('#taskRows').innerHTML = tasks
    .map(
      (t, idx) => `
    <div class="task-row" data-id="${t.id}">
      <span>${idx + 1}</span>
      <span class="task-title">${t.task_type === 'milestone' ? '<i class="milestone-ico"></i>' : phaseColorDot(t.phase)}<b title="${safe(t.title)}">${safe(t.title)}</b></span>
      <span title="${safe(t.owner)}">${safe(t.owner || '-')}</span>
      <span><div class="progress-mini"><i style="width:${clamp(t.progress, 0, 100)}%"></i></div>${t.progress}%</span>
      <span class="row-actions"><button class="icon-btn" onclick="openTaskModal(${Number(t.id)})">Editar</button><button class="icon-btn" onclick="removeTask(${Number(t.id)})">Borrar</button></span>
    </div>`
    )
    .join('');

  const { min, max, total } = timelineBounds();
  const pxPerDay = 18;
  const width = Math.max(900, total * pxPerDay);
  const header = $('#timelineHeader');
  const grid = $('#ganttGrid');
  header.style.width = `${width}px`;
  header.innerHTML = '';
  grid.style.width = `${width}px`;
  grid.style.height = `${Math.max(594, tasks.length * 37)}px`;
  const weeks = Math.ceil(total / 7);
  header.style.gridTemplateColumns = `repeat(${weeks}, 126px)`;
  for (let i = 0; i < weeks; i++) {
    const d = new Date(min);
    d.setDate(min.getDate() + i * 7);
    header.insertAdjacentHTML('beforeend', `<div class="time-cell">${d.toLocaleDateString('es-CO', { month: 'short', day: '2-digit' })}</div>`);
  }
  grid.innerHTML = '';
  for (let i = 0; i <= weeks; i++) grid.insertAdjacentHTML('beforeend', `<div class="grid-col" style="left:${i * 126}px"></div>`);
  tasks.forEach((t, idx) => {
    grid.insertAdjacentHTML('beforeend', `<div class="gantt-row-line" style="top:${idx * 37}px"></div>`);
    const start = Math.max(0, Math.round((parseDate(t.start_date) - min) / (1000 * 60 * 60 * 24)) * pxPerDay);
    const duration = Math.max(t.task_type === 'milestone' ? 1 : 2, (daysBetween(t.start_date, t.end_date) + 1) * pxPerDay);
    const top = idx * 37 + 8;
    if (t.task_type === 'milestone') {
      grid.insertAdjacentHTML('beforeend', `<div class="milestone" data-task="${Number(t.id)}" title="${safe(t.title)}" style="left:${start}px;top:${top + 1}px"></div>`);
    } else {
      grid.insertAdjacentHTML(
        'beforeend',
        `<div class="bar ${barClass(t.phase)}" data-task="${Number(t.id)}" title="${safe(t.title)}" style="left:${start}px;top:${top}px;width:${duration}px"><i class="bar-fill" style="width:${clamp(t.progress, 0, 100)}%"></i><span>${safe(t.title)}</span></div>`
      );
    }
  });
  const todayX = Math.round((new Date(new Date().toDateString()) - min) / (1000 * 60 * 60 * 24)) * pxPerDay;
  if (todayX >= 0 && todayX <= width) {
    grid.insertAdjacentHTML('beforeend', `<div class="today-line" style="left:${todayX}px"></div>`);
  }
  setTimeout(drawDependencies, 50);
}

export function drawDependencies() {
  const svg = $('#dependencySvg');
  const grid = $('#ganttGrid');
  const tasks = [...state.tasks].sort((a, b) => (a.order_index || 0) - (b.order_index || 0) || a.id - b.id);
  const rowById = Object.fromEntries(tasks.map((t, i) => [t.id, i]));
  svg.setAttribute('width', grid.scrollWidth);
  svg.setAttribute('height', grid.scrollHeight);
  svg.innerHTML = `<defs><marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#2563eb"></polygon></marker></defs>`;
  const { min } = timelineBounds();
  const pxPerDay = 18;
  state.dependencies.forEach((d) => {
    const pred = state.tasks.find((t) => t.id === d.predecessor_id),
      succ = state.tasks.find((t) => t.id === d.successor_id);
    if (!pred || !succ) return;
    const x1 = Math.round((parseDate(pred.end_date) - min) / (1000 * 60 * 60 * 24)) * pxPerDay + 12;
    const x2 = Math.round((parseDate(succ.start_date) - min) / (1000 * 60 * 60 * 24)) * pxPerDay - 3;
    const y1 = (rowById[pred.id] || 0) * 37 + 18;
    const y2 = (rowById[succ.id] || 0) * 37 + 18;
    const mid = Math.max(x1 + 12, (x1 + x2) / 2);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} L ${mid} ${y1} L ${mid} ${y2} L ${x2} ${y2}`);
    path.setAttribute('class', 'dependency-line');
    svg.appendChild(path);
  });
}

export function renderSidePanels() {
  const milestones = state.tasks.filter((t) => t.task_type === 'milestone').slice(0, 6);
  $('#milestonePanel').innerHTML = `<h3>Hitos clave</h3><div class="mini-list">${
    milestones
      .map(
        (m) =>
          `<div class="mini-list-item"><span><i class="diamond"></i><b>${safe(m.title)}</b><br><small>${safe(m.end_date)}</small></span><span class="pill ${m.progress === 100 ? 'pill-green' : ''}">${safe(m.status)}</span></div>`
      )
      .join('') || '<p>No hay hitos.</p>'
  }</div>`;
  const depTexts = state.dependencies
    .slice(0, 5)
    .map((d) => {
      const a = state.tasks.find((t) => t.id === d.predecessor_id),
        b = state.tasks.find((t) => t.id === d.successor_id);
      return a && b ? `<div class="dep-text"><b>${safe(a.title)}</b><br>→ ${safe(b.title)}</div>` : '';
    })
    .join('');
  $('#dependencyPanel').innerHTML = `<h3>Dependencias críticas</h3>${depTexts || '<p>No hay dependencias configuradas.</p>'}<small>Dependencias totales: ${state.dependencies.length}</small>`;
}

export function openTaskModal(id = null) {
  const t = id
    ? state.tasks.find((x) => x.id === id)
    : {
        project_id: state.current_project.id,
        title: '',
        phase: 'Ejecución',
        task_type: 'task',
        start_date: state.current_project.start_date,
        end_date: state.current_project.start_date,
        progress: 0,
        owner: '',
        status: 'Pendiente',
        story_points: 0,
        budget: 0,
        description: '',
        order_index: state.tasks.length + 1,
      };
  openModal(
    id ? 'Editar actividad' : 'Nueva actividad / hito',
    `<form id="taskForm"><div class="form-grid two">
    <label>Título<input name="title" value="${safe(t.title)}" required></label>
    <label>Tipo<select name="task_type"><option value="task" ${t.task_type === 'task' ? 'selected' : ''}>Actividad</option><option value="milestone" ${t.task_type === 'milestone' ? 'selected' : ''}>Hito</option></select></label>
    <label>Fase<select name="phase">${getPhasesOptions(t.phase)}</select></label>
    <label>Responsable<select name="owner">${getResourceNamesOptions(t.owner)}</select></label>
    <label>Fecha inicio<input name="start_date" type="date" value="${t.start_date}" required></label>
    <label>Fecha fin<input name="end_date" type="date" value="${t.end_date}" required></label>
    <label>Avance %<input name="progress" type="number" min="0" max="100" value="${t.progress || 0}"></label>
    <label>Estado<input name="status" value="${safe(t.status || 'Pendiente')}"></label>
    <label>Story points<input name="story_points" type="number" min="0" value="${t.story_points || 0}"></label>
    <label>Presupuesto<input name="budget" type="number" min="0" value="${t.budget || 0}"></label>
    ${id ? '' : `<label>Depende de<select name="predecessor_id">${getTaskOptions('')}</select></label>`}
    <label>Orden<input name="order_index" type="number" value="${t.order_index || state.tasks.length + 1}"></label>
  </div><label>Descripción<textarea name="description" rows="3">${safe(t.description || '')}</textarea></label>${modalActions(id ? 'Actualizar' : 'Crear')}</form>`
  );
  $('#taskForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    body.project_id = state.current_project.id;
    body.progress = Number(body.progress || 0);
    body.story_points = Number(body.story_points || 0);
    body.budget = Number(body.budget || 0);
    body.order_index = Number(body.order_index || 0);
    if (!body.predecessor_id) delete body.predecessor_id;
    else body.predecessor_id = Number(body.predecessor_id);
    if (id) await api.updateTask(id, body);
    else await api.createTask(body);
    closeModal();
    toast(id ? 'Actividad actualizada' : 'Actividad creada');
    await load(state.current_project.id);
  });
}

export async function removeTask(id) {
  if (!confirm('¿Eliminar esta actividad y sus dependencias?')) return;
  await api.deleteTask(id);
  toast('Actividad eliminada');
  await load(state.current_project.id);
}
