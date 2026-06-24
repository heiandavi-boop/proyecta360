// AI view: deterministic plan generation and executive report generation.
import { $, toast } from '../dom.js';
import { state } from '../state.js';
import * as api from '../api.js';
import { load, renderView } from '../main.js';

export async function aiGeneratePlan() {
  const body = {
    project_id: state.current_project.id,
    objective: $('#aiObjective').value,
    execution_methodology: $('#aiMethodology').value,
    horizon_weeks: Number($('#aiWeeks').value || 12),
    create_records: true,
  };
  const res = await api.aiGeneratePlan(body);
  $('#aiOutput').textContent =
    `${res.message}\n\nActividades generadas:\n` +
    res.generated_tasks.map((t, i) => `${i + 1}. ${t.title} | ${t.phase} | ${t.start_date} → ${t.end_date}`).join('\n');
  toast('Plan generado y agregado al Gantt');
  await load(state.current_project.id);
  renderView('ai');
}

export async function aiGenerateReport() {
  const res = await api.aiReport({ project_id: state.current_project.id, audience: 'Comité Directivo' });
  $('#aiOutput').textContent = res.report;
  renderView('ai');
}
