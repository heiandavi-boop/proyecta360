// Parameters view: the project configuration form, plus collecting and
// saving those parameters. Also hosts the "new project" creation modal.
import { $, escapeHtml, iso, toast } from '../dom.js';
import { state } from '../state.js';
import { openModal, closeModal, modalActions } from '../modal.js';
import * as api from '../api.js';
import { load, renderView } from '../main.js';

export function renderParameters() {
  const p = state.current_project;
  const params = p.parameters || state.defaults;
  const phases = (params.phases || []).join(', '),
    tStatuses = (params.task_statuses || []).join(', '),
    sStatuses = (params.story_statuses || []).join(', '),
    methods = (params.execution_methodologies || []).join(', ');
  $('#parametersForm').innerHTML = `
    <div class="parameter-block"><h3>Datos generales del proyecto</h3><div class="form-grid">
      <label>Nombre<input id="param_name" value="${escapeHtml(p.name)}"></label>
      <label>Project Manager<input id="param_pm" value="${escapeHtml(p.project_manager || '')}"></label>
      <label>Sponsor<input id="param_sponsor" value="${escapeHtml(p.sponsor || '')}"></label>
      <label>Fecha inicio<input id="param_start" type="date" value="${p.start_date}"></label>
      <label>Fecha fin<input id="param_end" type="date" value="${p.end_date}"></label>
      <label>Presupuesto<input id="param_budget" type="number" value="${p.budget || 0}"></label>
      <label>Moneda<input id="param_currency" value="${p.currency || 'COP'}"></label>
      <label>Estado<select id="param_status"><option>Planeado</option><option>En ejecución</option><option>En riesgo</option><option>Cerrado</option></select></label>
      <label>Metodología control<input id="param_methodology" value="${escapeHtml(p.methodology)}"></label>
    </div></div>
    <div class="parameter-block"><h3>Modelo de control y ejecución</h3><div class="form-grid two">
      <label>Modelo de control<textarea id="param_control" rows="3">${escapeHtml(params.control_model || '')}</textarea></label>
      <label>Metodologías permitidas<textarea id="param_methods" rows="3">${escapeHtml(methods)}</textarea><span class="field-help">Separadas por coma.</span></label>
      <label>Metodología seleccionada<input id="param_selected_method" value="${escapeHtml(params.selected_execution_methodology || 'Scrum')}"></label>
      <label>Duración del sprint días<input id="param_sprint_days" type="number" min="1" value="${params.sprint?.duration_days || 14}"></label>
    </div></div>
    <div class="parameter-block"><h3>Calendario y flujo de trabajo</h3><div class="form-grid">
      <label>Días laborales<input id="param_working_days" value="${escapeHtml((params.calendar?.working_days || []).join(', '))}"></label>
      <label>Hora inicio<input id="param_work_start" type="time" value="${params.calendar?.workday_start || '08:00'}"></label>
      <label>Hora fin<input id="param_work_end" type="time" value="${params.calendar?.workday_end || '17:00'}"></label>
      <label>Zona horaria<input id="param_timezone" value="${params.calendar?.timezone || 'America/Bogota'}"></label>
      <label>Fases PMP / híbridas<textarea id="param_phases" rows="3">${escapeHtml(phases)}</textarea></label>
      <label>Estados de actividades<textarea id="param_task_statuses" rows="3">${escapeHtml(tStatuses)}</textarea></label>
      <label>Estados Scrum<textarea id="param_story_statuses" rows="3">${escapeHtml(sStatuses)}</textarea></label>
    </div></div>
    <div class="parameter-block"><h3>Matriz de riesgo, gobierno e IA</h3><div class="form-grid">
      <label>Umbral riesgo medio<input id="param_medium" type="number" value="${params.risk_matrix?.medium_threshold || 8}"></label>
      <label>Umbral riesgo alto<input id="param_high" type="number" value="${params.risk_matrix?.high_threshold || 15}"></label>
      <label class="inline-check"><input id="param_cp" type="checkbox" ${params.governance?.critical_path_enabled ? 'checked' : ''}> Ruta crítica activa</label>
      <label class="inline-check"><input id="param_budget_control" type="checkbox" ${params.governance?.budget_control_enabled ? 'checked' : ''}> Control de presupuesto</label>
      <label class="inline-check"><input id="param_weekly" type="checkbox" ${params.governance?.weekly_status_report ? 'checked' : ''}> Reporte semanal</label>
      <label class="inline-check"><input id="param_ai_enabled" type="checkbox" ${params.ai?.enabled ? 'checked' : ''}> IA habilitada</label>
      <label>Proveedor IA<input id="param_ai_provider" value="${escapeHtml(params.ai?.provider || 'OpenAI / Azure OpenAI')}"></label>
      <label>Modelo IA<input id="param_ai_model" value="${escapeHtml(params.ai?.model || 'configurable')}"></label>
    </div></div>`;
  $('#param_status').value = p.status;
}

function collectParameters() {
  const split = (v) =>
    String(v || '')
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean);
  const params = {
    control_model: $('#param_control').value,
    execution_methodologies: split($('#param_methods').value),
    selected_execution_methodology: $('#param_selected_method').value,
    calendar: {
      working_days: split($('#param_working_days').value),
      workday_start: $('#param_work_start').value,
      workday_end: $('#param_work_end').value,
      timezone: $('#param_timezone').value,
    },
    phases: split($('#param_phases').value),
    task_statuses: split($('#param_task_statuses').value),
    story_statuses: split($('#param_story_statuses').value),
    sprint: { duration_days: Number($('#param_sprint_days').value || 14), story_point_scale: [1, 2, 3, 5, 8, 13] },
    risk_matrix: {
      probability_scale: [1, 2, 3, 4, 5],
      impact_scale: [1, 2, 3, 4, 5],
      medium_threshold: Number($('#param_medium').value || 8),
      high_threshold: Number($('#param_high').value || 15),
    },
    governance: {
      critical_path_enabled: $('#param_cp').checked,
      budget_control_enabled: $('#param_budget_control').checked,
      weekly_status_report: $('#param_weekly').checked,
      stage_gate_approval: true,
    },
    ai: {
      enabled: $('#param_ai_enabled').checked,
      provider: $('#param_ai_provider').value,
      model: $('#param_ai_model').value,
      use_project_documents: true,
      allow_create_tasks: true,
      allow_create_risks: true,
    },
  };
  return {
    name: $('#param_name').value,
    project_manager: $('#param_pm').value,
    sponsor: $('#param_sponsor').value,
    start_date: $('#param_start').value,
    end_date: $('#param_end').value,
    budget: Number($('#param_budget').value || 0),
    currency: $('#param_currency').value,
    status: $('#param_status').value,
    methodology: $('#param_methodology').value,
    parameters: params,
  };
}

export async function saveParameters() {
  await api.updateProject(state.current_project.id, collectParameters());
  toast('Parámetros guardados');
  await load(state.current_project.id);
}

export function openNewProjectModal() {
  const today = iso(new Date());
  const end = new Date();
  end.setDate(end.getDate() + 90);
  openModal(
    'Nuevo proyecto parametrizable',
    `<form id="projectForm"><div class="form-grid two">
    <label>Nombre<input name="name" required value="Nuevo proyecto"></label>
    <label>Project Manager<input name="project_manager" value=""></label>
    <label>Sponsor<input name="sponsor" value=""></label>
    <label>Fecha inicio<input name="start_date" type="date" value="${today}"></label>
    <label>Fecha fin<input name="end_date" type="date" value="${iso(end)}"></label>
    <label>Presupuesto<input name="budget" type="number" value="0"></label>
    <label>Moneda<input name="currency" value="COP"></label>
    <label>Metodología<select name="methodology"><option>Híbrida PMP + Scrum</option><option>Tradicional PMP</option><option>Ágil Scrum</option><option>Híbrida personalizada</option></select></label>
  </div><label>Descripción<textarea name="description" rows="3">Proyecto creado desde Proyecta360.</textarea></label>${modalActions('Crear proyecto')}</form>`
  );
  $('#projectForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    body.budget = Number(body.budget || 0);
    body.status = 'Planeado';
    body.parameters = state.defaults;
    const created = await api.createProject(body);
    closeModal();
    toast('Proyecto creado');
    await load(created.id);
    renderView('parameters');
  });
}
