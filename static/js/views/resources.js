// Resources view: capacity cards and the resource editor modal.
import { $, safe, clamp, toast } from '../dom.js';
import { state } from '../state.js';
import { openModal, closeModal, modalActions } from '../modal.js';
import * as api from '../api.js';
import { load } from '../main.js';

export function renderResources() {
  $('#resourceGrid').innerHTML =
    state.resources
      .map(
        (r) =>
          `<div class="resource-card"><div class="avatar">${safe(
            r.name
              .split(' ')
              .map((x) => x[0])
              .slice(0, 2)
              .join('')
          )}</div><h3>${safe(r.name)}</h3><p><b>${safe(r.role || 'Rol pendiente')}</b><br>${safe(r.email || '')}</p><span class="pill">Capacidad ${Number(
            r.capacity
          )}%</span><div class="capacity-bar"><i style="width:${clamp(r.capacity, 0, 100)}%"></i></div></div>`
      )
      .join('') || '<p>No hay recursos.</p>';
}

export function openResourceModal() {
  openModal(
    'Nuevo recurso',
    `<form id="resourceForm"><div class="form-grid two">
    <label>Nombre<input name="name" required></label>
    <label>Rol<input name="role"></label>
    <label>Email<input name="email" type="email"></label>
    <label>Capacidad %<input name="capacity" type="number" min="0" max="100" value="100"></label>
  </div>${modalActions('Crear')}</form>`
  );
  $('#resourceForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    body.project_id = state.current_project.id;
    body.capacity = Number(body.capacity || 100);
    await api.createResource(body);
    closeModal();
    toast('Recurso creado');
    await load(state.current_project.id);
  });
}
