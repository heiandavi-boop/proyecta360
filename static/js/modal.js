// Shared modal primitives and the <select> option builders used by the
// entity forms (tasks, stories, risks, resources, projects).
import { $, safe } from './dom.js';
import { state } from './state.js';

export function openModal(title, html) {
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = html;
  $('#entityModal').classList.remove('hidden');
}

export function closeModal() {
  $('#entityModal').classList.add('hidden');
}

export function modalActions(submitLabel = 'Guardar') {
  return `<div class="modal-actions"><button class="btn ghost" data-close="modal">Cancelar</button><button class="btn primary" type="submit">${submitLabel}</button></div>`;
}

export function getPhasesOptions(selected = '') {
  return (state.current_project.parameters?.phases || ['Inicio', 'Planeación', 'Ejecución', 'Pruebas', 'Cierre'])
    .map((x) => `<option ${x === selected ? 'selected' : ''}>${safe(x)}</option>`)
    .join('');
}

export function getTaskOptions(selected = '') {
  return (
    `<option value="">Sin dependencia</option>` +
    state.tasks.map((t) => `<option value="${Number(t.id)}" ${t.id === selected ? 'selected' : ''}>${safe(t.title)}</option>`).join('')
  );
}

export function getSprintOptions(selected) {
  return (
    `<option value="">Sin sprint</option>` +
    state.sprints.map((s) => `<option value="${Number(s.id)}" ${s.id === selected ? 'selected' : ''}>${safe(s.name)}</option>`).join('')
  );
}

export function getResourceNamesOptions(selected = '') {
  return ['']
    .concat(state.resources.map((r) => r.name))
    .map((x) => `<option ${x === selected ? 'selected' : ''}>${safe(x)}</option>`)
    .join('');
}
