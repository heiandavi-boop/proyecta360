// Scrum view: sprint metrics, burndown chart, board columns and the
// story editor modal. Story movement updates a single story via the API.
import { $, safe, jsArg, toast } from '../dom.js';
import { state } from '../state.js';
import { openModal, closeModal, modalActions, getSprintOptions, getResourceNamesOptions } from '../modal.js';
import * as api from '../api.js';
import { load } from '../main.js';

export function renderScrum() {
  const activeSprint = state.sprints.find((s) => s.status === 'En curso') || state.sprints[0];
  const sprintStories = state.stories.filter((s) => !activeSprint || s.sprint_id === activeSprint.id);
  const total = sprintStories.reduce((a, s) => a + s.points, 0);
  const done = sprintStories.filter((s) => s.status === 'Hecho').reduce((a, s) => a + s.points, 0);
  $('#sprintMetrics').innerHTML = `
    <div class="metric-card"><span>Sprint actual</span><strong>${activeSprint ? safe(activeSprint.name) : 'N/A'}</strong><small>${activeSprint ? `${safe(activeSprint.start_date)} → ${safe(activeSprint.end_date)}` : ''}</small></div>
    <div class="metric-card"><span>Velocidad</span><strong>${activeSprint?.velocity || 0}</strong><small>puntos promedio</small></div>
    <div class="metric-card"><span>Comprometido</span><strong>${total}</strong><small>story points</small></div>
    <div class="metric-card"><span>Completado</span><strong>${done}</strong><small>${total ? Math.round((done / total) * 100) : 0}% del sprint</small></div>`;
  renderBurndown(total, done);
  const statuses = state.current_project.parameters?.story_statuses || ['Por hacer', 'En progreso', 'Hecho'];
  $('#scrumBoard').innerHTML = statuses
    .map((st) => {
      const cards = sprintStories
        .filter((s) => s.status === st)
        .map((s) => storyCard(s, statuses))
        .join('');
      return `<div class="board-col"><h3>${safe(st)}<span>${sprintStories.filter((s) => s.status === st).length}</span></h3>${cards || '<small>Sin historias</small>'}</div>`;
    })
    .join('');
}

function storyCard(s, statuses) {
  const idx = statuses.indexOf(s.status);
  return `<div class="story-card"><b>${safe(s.title)}</b><p>${safe(s.assignee || 'Sin responsable')} · ${safe(s.priority)}</p><div class="story-footer"><span class="pill">${Number(s.points)} pts</span><span class="move-actions">${
    idx > 0 ? `<button onclick="moveStory(${Number(s.id)}, ${jsArg(statuses[idx - 1])})">←</button>` : ''
  }${idx < statuses.length - 1 ? `<button onclick="moveStory(${Number(s.id)}, ${jsArg(statuses[idx + 1])})">→</button>` : ''}</span></div></div>`;
}

function renderBurndown(total, done) {
  const chart = $('#burndown');
  chart.innerHTML = '';
  const remaining = Math.max(0, total - done);
  const points = [total, Math.round(total * 0.8), Math.round(total * 0.62), Math.round(total * 0.45), remaining];
  const max = Math.max(total, 1),
    w = 240,
    h = 145;
  for (let i = 0; i < points.length - 1; i++) {
    const x1 = i * (w / (points.length - 1)) + 18,
      y1 = h - (points[i] / max) * h + 8;
    const x2 = (i + 1) * (w / (points.length - 1)) + 18,
      y2 = h - (points[i + 1] / max) * h + 8;
    const dx = x2 - x1,
      dy = y2 - y1,
      len = Math.sqrt(dx * dx + dy * dy),
      ang = (Math.atan2(dy, dx) * 180) / Math.PI;
    chart.insertAdjacentHTML('beforeend', `<div class="chart-line" style="left:${x1}px;top:${y1}px;width:${len}px;transform:rotate(${ang}deg)"></div>`);
    chart.insertAdjacentHTML('beforeend', `<div class="chart-dot" style="left:${x1 - 4}px;top:${y1 - 4}px"></div>`);
  }
  const lastX = (points.length - 1) * (w / (points.length - 1)) + 18,
    lastY = h - (points.at(-1) / max) * h + 8;
  chart.insertAdjacentHTML('beforeend', `<div class="chart-dot" style="left:${lastX - 4}px;top:${lastY - 4}px"></div>`);
}

export async function moveStory(id, status) {
  const s = state.stories.find((x) => x.id === id);
  if (!s) return;
  await api.updateStory(id, { ...s, status });
  toast('Historia actualizada');
  await load(state.current_project.id);
}

export function openStoryModal() {
  openModal(
    'Nueva historia de usuario',
    `<form id="storyForm"><div class="form-grid two">
    <label>Título<input name="title" required placeholder="US-27 Nueva funcionalidad"></label>
    <label>Sprint<select name="sprint_id">${getSprintOptions()}</select></label>
    <label>Estado<select name="status"><option>Por hacer</option><option>En progreso</option><option>Hecho</option></select></label>
    <label>Puntos<input name="points" type="number" value="5" min="0"></label>
    <label>Responsable<select name="assignee">${getResourceNamesOptions()}</select></label>
    <label>Prioridad<select name="priority"><option>Alta</option><option selected>Media</option><option>Baja</option></select></label>
  </div>${modalActions('Crear')}</form>`
  );
  $('#storyForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    body.project_id = state.current_project.id;
    body.points = Number(body.points || 0);
    body.sprint_id = body.sprint_id ? Number(body.sprint_id) : null;
    await api.createStory(body);
    closeModal();
    toast('Historia creada');
    await load(state.current_project.id);
  });
}
