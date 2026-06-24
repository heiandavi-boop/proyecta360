// Portfolio view: header, KPI strip, and the executive project grid.
import { $, fmt, safe } from '../dom.js';
import { state } from '../state.js';

export function renderHeader() {
  const p = state.current_project;
  if (!p) return;
  $('#projectTitle').textContent = p.name;
  $('#projectDescription').textContent = p.description || 'Sin descripción registrada.';
  $('#projectMethodology').textContent = p.methodology;
  $('#projectStatus').textContent = p.status;
  $('#projectDates').textContent = `${p.start_date} → ${p.end_date}`;
  const sel = $('#projectSelector');
  sel.innerHTML = state.projects
    .map((pr) => `<option value="${Number(pr.id)}" ${pr.id === p.id ? 'selected' : ''}>${safe(pr.name)}</option>`)
    .join('');
}

export function renderKpis() {
  const m = state.metrics,
    p = state.current_project;
  $('#kpiStrip').innerHTML = `
    <div class="kpi"><span>Avance general</span><strong>${m.progress ?? 0}%</strong><small>Plan consolidado</small></div>
    <div class="kpi"><span>Presupuesto ejecutado</span><strong>$${fmt.format(Math.round(m.spent || 0))}</strong><small>de $${fmt.format(Math.round(m.budget || 0))} ${safe(p.currency)}</small></div>
    <div class="kpi"><span>Riesgos abiertos</span><strong>${m.open_risks ?? 0}</strong><small>Altos: ${m.high_risks ?? 0}</small></div>
    <div class="kpi"><span>Ruta crítica</span><strong>${m.critical_path_tasks ?? 0}</strong><small>Tareas con dependencias</small></div>
    <div class="kpi"><span>Estado del proyecto</span><strong>${m.health ?? 'N/A'}</strong><small>${m.delayed_tasks ?? 0} tareas atrasadas</small></div>`;
  const donut = $('#progressDonut');
  if (donut) {
    donut.style.setProperty('--value', state.metrics.progress || 0);
    donut.querySelector('span').textContent = `${state.metrics.progress || 0}%`;
  }
}

export function renderPortfolio() {
  $('#portfolioGrid').innerHTML = state.projects
    .map((p) => {
      const current = p.id === state.current_project.id;
      return `<div class="portfolio-card">
      <span class="pill ${current ? 'pill-blue' : ''}">${current ? 'Activo' : 'Proyecto'}</span>
      <h3>${safe(p.name)}</h3><p>${safe(p.description || 'Sin descripción')}</p>
      <p><b>PM:</b> ${safe(p.project_manager || 'N/A')}<br><b>Metodología:</b> ${safe(p.methodology)}<br><b>Fechas:</b> ${safe(p.start_date)} → ${safe(p.end_date)}</p>
      <button class="btn small" onclick="load(${Number(p.id)})">Abrir</button>
    </div>`;
    })
    .join('');
}
