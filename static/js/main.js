// Entry point: orchestrates data loading, view switching, navigation/tabs,
// the modal, global listeners and the window-level handlers used by inline
// onclick attributes in rendered HTML.
import { $, $$, toast } from './dom.js';
import { state, setState } from './state.js';
import * as api from './api.js';
import { closeModal } from './modal.js';
import { renderHeader, renderKpis, renderPortfolio } from './views/portfolio.js';
import { renderGantt, drawDependencies, renderSidePanels, openTaskModal, removeTask } from './views/gantt.js';
import { renderScrum, moveStory, openStoryModal } from './views/scrum.js';
import { renderRisks, openRiskModal } from './views/risks.js';
import { renderResources, openResourceModal } from './views/resources.js';
import { renderParameters, saveParameters, openNewProjectModal } from './views/parameters.js';
import { aiGeneratePlan, aiGenerateReport } from './views/ai.js';

export async function load(projectId) {
  setState(await api.bootstrap(projectId));
  renderAll();
}

function renderAll() {
  renderHeader();
  renderKpis();
  renderPortfolio();
  renderGantt();
  renderSidePanels();
  renderScrum();
  renderRisks();
  renderResources();
  renderParameters();
  renderView(state.view);
}

export function renderView(view) {
  state.view = view;
  $$('.view').forEach((v) => v.classList.add('hidden'));
  const el = $(`#view-${view}`) || $('#view-gantt');
  el.classList.remove('hidden');
  $$('.side-item,.top-tab').forEach((b) =>
    b.classList.toggle('active', b.dataset.view === view || (view === 'gantt' && ['Plan Maestro', 'Gantt'].includes(b.textContent.trim())))
  );
  if (view === 'gantt') setTimeout(drawDependencies, 50);
}

function bindEvents() {
  $$('.side-item,.top-tab').forEach((b) => b.addEventListener('click', () => renderView(b.dataset.view || 'gantt')));
  $('#projectSelector').addEventListener('change', (e) => load(Number(e.target.value)));
  $('#btnReload').addEventListener('click', () => load(state.current_project.id));
  $('#btnAddTask').addEventListener('click', () => openTaskModal());
  $('#btnAiPlan').addEventListener('click', () => {
    renderView('ai');
    $('#aiObjective').focus();
  });
  $('#btnOpenParameters').addEventListener('click', () => renderView('parameters'));
  $('#btnSaveParametersInline').addEventListener('click', saveParameters);
  $('#btnNewProject').addEventListener('click', openNewProjectModal);
  $('#btnAddStory').addEventListener('click', openStoryModal);
  $('#btnAddRisk').addEventListener('click', openRiskModal);
  $('#btnAddResource').addEventListener('click', openResourceModal);
  $('#btnGeneratePlan').addEventListener('click', aiGeneratePlan);
  $('#btnGenerateReport').addEventListener('click', aiGenerateReport);
  $$('[data-close="modal"]').forEach((x) => x.addEventListener('click', closeModal));
  $('#entityModal').addEventListener('click', (e) => {
    if (e.target.dataset.close === 'modal') closeModal();
  });
  window.addEventListener('resize', () => state.view === 'gantt' && drawDependencies());
}

// Exposed globally for inline onclick handlers inside dynamically rendered HTML.
window.openTaskModal = openTaskModal;
window.removeTask = removeTask;
window.moveStory = moveStory;
window.load = load;

bindEvents();
load().catch((err) => {
  console.error(err);
  toast(err.message);
});
