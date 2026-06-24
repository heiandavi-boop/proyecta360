// Risks view: probability/impact/level matrix table and the risk editor modal.
import { $, safe, toast } from '../dom.js';
import { state } from '../state.js';
import { openModal, closeModal, modalActions, getResourceNamesOptions } from '../modal.js';
import * as api from '../api.js';
import { load } from '../main.js';

export function renderRisks() {
  $('#riskTable').innerHTML =
    `<div class="table-row header"><span>Riesgo</span><span>Prob.</span><span>Impacto</span><span>Nivel</span><span>Respuesta</span><span>Estado</span></div>` +
    state.risks
      .map(
        (r) =>
          `<div class="table-row"><b>${safe(r.title)}</b><span>${Number(r.probability)}</span><span>${Number(r.impact)}</span><span class="pill ${
            r.level === 'Alto' ? 'pill-red' : r.level === 'Medio' ? 'pill-amber' : 'pill-green'
          }">${safe(r.level)}</span><span>${safe(r.response || '-')}</span><span>${safe(r.status)}</span></div>`
      )
      .join('');
}

export function openRiskModal() {
  openModal(
    'Nuevo riesgo',
    `<form id="riskForm"><div class="form-grid two">
    <label>Riesgo<input name="title" required></label>
    <label>Responsable<select name="owner">${getResourceNamesOptions()}</select></label>
    <label>Probabilidad 1-5<input name="probability" type="number" min="1" max="5" value="3"></label>
    <label>Impacto 1-5<input name="impact" type="number" min="1" max="5" value="3"></label>
    <label>Estado<select name="status"><option>Abierto</option><option>Mitigado</option><option>Cerrado</option></select></label>
  </div><label>Respuesta<textarea name="response" rows="3"></textarea></label>${modalActions('Crear')}</form>`
  );
  $('#riskForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    body.project_id = state.current_project.id;
    body.probability = Number(body.probability || 1);
    body.impact = Number(body.impact || 1);
    await api.createRisk(body);
    closeModal();
    toast('Riesgo creado');
    await load(state.current_project.id);
  });
}
