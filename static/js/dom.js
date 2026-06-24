// Small shared DOM and formatting helpers. No app-specific logic here.

export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => Array.from(document.querySelectorAll(sel));

export const fmt = new Intl.NumberFormat('es-CO');

export const slug = (value = '') =>
  String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'custom';

export const knownPhase = (phase = '') =>
  ['Inicio', 'Planeacion', 'Ejecucion', 'Pruebas', 'Cierre'].includes(slug(phase)) ? slug(phase) : 'custom';

export const phaseClass = (phase = '') => `phase-${knownPhase(phase)}`;
export const barClass = (phase = '') => `bar-${knownPhase(phase)}`;

export const parseDate = (d) => new Date(`${d}T00:00:00`);
export const iso = (d) => d.toISOString().slice(0, 10);
export const daysBetween = (a, b) => Math.round((parseDate(b) - parseDate(a)) / (1000 * 60 * 60 * 24));
export const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

export function escapeHtml(str = '') {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export const safe = escapeHtml;
export const jsArg = (value) => safe(JSON.stringify(value));

export function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3300);
}
