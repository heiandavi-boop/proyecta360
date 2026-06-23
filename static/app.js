const API = '';
const state = {
  projects: [], current_project: null, tasks: [], dependencies: [], sprints: [], stories: [], risks: [], resources: [], metrics: {}, defaults: {}, view: 'gantt'
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const fmt = new Intl.NumberFormat('es-CO');
const slug = (value='') => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '') || 'custom';
const knownPhase = (phase='') => ['Inicio','Planeacion','Ejecucion','Pruebas','Cierre'].includes(slug(phase)) ? slug(phase) : 'custom';
const phaseClass = (phase='') => `phase-${knownPhase(phase)}`;
const barClass = (phase='') => `bar-${knownPhase(phase)}`;
const parseDate = (d) => new Date(`${d}T00:00:00`);
const iso = (d) => d.toISOString().slice(0,10);
const daysBetween = (a,b) => Math.round((parseDate(b)-parseDate(a))/(1000*60*60*24));
const clamp = (v,min,max) => Math.max(min, Math.min(max, v));
function escapeHtml(str=''){ return String(str).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#39;"); }
const safe = escapeHtml;
const jsArg = (value) => safe(JSON.stringify(value));
function toast(msg){ const el=$('#toast'); el.textContent=msg; el.classList.remove('hidden'); setTimeout(()=>el.classList.add('hidden'), 3300); }

async function request(path, options={}){
  const res = await fetch(`${API}${path}`, {headers:{'Content-Type':'application/json'}, ...options});
  if(!res.ok){
    let detail = 'Error en la operación';
    try{ detail = (await res.json()).detail || detail; }catch(e){}
    throw new Error(detail);
  }
  return res.json();
}
async function load(projectId){
  const query = projectId ? `?project_id=${projectId}` : '';
  Object.assign(state, await request(`/api/bootstrap${query}`));
  renderAll();
}

function renderAll(){
  renderHeader(); renderKpis(); renderPortfolio(); renderGantt(); renderSidePanels(); renderScrum(); renderRisks(); renderResources(); renderParameters(); renderView(state.view);
}
function renderHeader(){
  const p = state.current_project; if(!p) return;
  $('#projectTitle').textContent = p.name;
  $('#projectDescription').textContent = p.description || 'Sin descripción registrada.';
  $('#projectMethodology').textContent = p.methodology;
  $('#projectStatus').textContent = p.status;
  $('#projectDates').textContent = `${p.start_date} → ${p.end_date}`;
  const sel = $('#projectSelector');
  sel.innerHTML = state.projects.map(pr => `<option value="${Number(pr.id)}" ${pr.id===p.id?'selected':''}>${safe(pr.name)}</option>`).join('');
}
function renderKpis(){
  const m=state.metrics, p=state.current_project;
  $('#kpiStrip').innerHTML = `
    <div class="kpi"><span>Avance general</span><strong>${m.progress ?? 0}%</strong><small>Plan consolidado</small></div>
    <div class="kpi"><span>Presupuesto ejecutado</span><strong>$${fmt.format(Math.round(m.spent || 0))}</strong><small>de $${fmt.format(Math.round(m.budget || 0))} ${safe(p.currency)}</small></div>
    <div class="kpi"><span>Riesgos abiertos</span><strong>${m.open_risks ?? 0}</strong><small>Altos: ${m.high_risks ?? 0}</small></div>
    <div class="kpi"><span>Ruta crítica</span><strong>${m.critical_path_tasks ?? 0}</strong><small>Tareas con dependencias</small></div>
    <div class="kpi"><span>Estado del proyecto</span><strong>${m.health ?? 'N/A'}</strong><small>${m.delayed_tasks ?? 0} tareas atrasadas</small></div>`;
  const donut = $('#progressDonut'); if(donut){ donut.style.setProperty('--value', state.metrics.progress || 0); donut.querySelector('span').textContent = `${state.metrics.progress || 0}%`; }
}
function renderPortfolio(){
  $('#portfolioGrid').innerHTML = state.projects.map(p => {
    const current = p.id === state.current_project.id;
    return `<div class="portfolio-card">
      <span class="pill ${current?'pill-blue':''}">${current?'Activo':'Proyecto'}</span>
      <h3>${safe(p.name)}</h3><p>${safe(p.description || 'Sin descripción')}</p>
      <p><b>PM:</b> ${safe(p.project_manager || 'N/A')}<br><b>Metodología:</b> ${safe(p.methodology)}<br><b>Fechas:</b> ${safe(p.start_date)} → ${safe(p.end_date)}</p>
      <button class="btn small" onclick="load(${Number(p.id)})">Abrir</button>
    </div>`;
  }).join('');
}
function timelineBounds(){
  const p = state.current_project;
  let min = parseDate(p.start_date), max = parseDate(p.end_date);
  state.tasks.forEach(t=>{ min = parseDate(t.start_date) < min ? parseDate(t.start_date) : min; max = parseDate(t.end_date) > max ? parseDate(t.end_date) : max; });
  min.setDate(min.getDate()-3); max.setDate(max.getDate()+7);
  return {min, max, total: Math.max(1, Math.round((max-min)/(1000*60*60*24)))};
}
function phaseColorDot(phase){ return `<i class="phase-dot ${phaseClass(phase)}"></i>`; }
function renderGantt(){
  const tasks = [...state.tasks].sort((a,b)=>(a.order_index||0)-(b.order_index||0)||a.id-b.id);
  $('#taskRows').innerHTML = tasks.map((t,idx)=>`
    <div class="task-row" data-id="${t.id}">
      <span>${idx+1}</span>
      <span class="task-title">${t.task_type==='milestone'?'<i class="milestone-ico"></i>':phaseColorDot(t.phase)}<b title="${safe(t.title)}">${safe(t.title)}</b></span>
      <span title="${safe(t.owner)}">${safe(t.owner || '-')}</span>
      <span><div class="progress-mini"><i style="width:${clamp(t.progress,0,100)}%"></i></div>${t.progress}%</span>
      <span class="row-actions"><button class="icon-btn" onclick="openTaskModal(${Number(t.id)})">Editar</button><button class="icon-btn" onclick="removeTask(${Number(t.id)})">Borrar</button></span>
    </div>`).join('');

  const {min,max,total} = timelineBounds();
  const pxPerDay = 18;
  const width = Math.max(900, total * pxPerDay);
  const header = $('#timelineHeader');
  const grid = $('#ganttGrid');
  header.style.width = `${width}px`;
  header.innerHTML = '';
  grid.style.width = `${width}px`;
  grid.style.height = `${Math.max(594, tasks.length*37)}px`;
  const weeks = Math.ceil(total/7);
  header.style.gridTemplateColumns = `repeat(${weeks}, 126px)`;
  for(let i=0;i<weeks;i++){
    const d = new Date(min); d.setDate(min.getDate()+i*7);
    header.insertAdjacentHTML('beforeend', `<div class="time-cell">${d.toLocaleDateString('es-CO',{month:'short',day:'2-digit'})}</div>`);
  }
  grid.innerHTML = '';
  for(let i=0;i<=weeks;i++) grid.insertAdjacentHTML('beforeend', `<div class="grid-col" style="left:${i*126}px"></div>`);
  tasks.forEach((t,idx)=>{
    grid.insertAdjacentHTML('beforeend', `<div class="gantt-row-line" style="top:${idx*37}px"></div>`);
    const start = Math.max(0, Math.round((parseDate(t.start_date)-min)/(1000*60*60*24))*pxPerDay);
    const duration = Math.max(t.task_type==='milestone'?1:2, (daysBetween(t.start_date,t.end_date)+1)*pxPerDay);
    const top = idx*37 + 8;
    if(t.task_type === 'milestone'){
      grid.insertAdjacentHTML('beforeend', `<div class="milestone" data-task="${Number(t.id)}" title="${safe(t.title)}" style="left:${start}px;top:${top+1}px"></div>`);
    }else{
      grid.insertAdjacentHTML('beforeend', `<div class="bar ${barClass(t.phase)}" data-task="${Number(t.id)}" title="${safe(t.title)}" style="left:${start}px;top:${top}px;width:${duration}px"><i class="bar-fill" style="width:${clamp(t.progress,0,100)}%"></i><span>${safe(t.title)}</span></div>`);
    }
  });
  const todayX = Math.round((new Date(new Date().toDateString())-min)/(1000*60*60*24))*pxPerDay;
  if(todayX >=0 && todayX <= width){ grid.insertAdjacentHTML('beforeend', `<div class="today-line" style="left:${todayX}px"></div>`); }
  setTimeout(drawDependencies, 50);
}
function drawDependencies(){
  const svg = $('#dependencySvg'); const grid=$('#ganttGrid'); const wrap=$('.timeline-wrap');
  const tasks = [...state.tasks].sort((a,b)=>(a.order_index||0)-(b.order_index||0)||a.id-b.id);
  const rowById = Object.fromEntries(tasks.map((t,i)=>[t.id,i]));
  svg.setAttribute('width', grid.scrollWidth); svg.setAttribute('height', grid.scrollHeight); svg.innerHTML = `<defs><marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#2563eb"></polygon></marker></defs>`;
  const {min} = timelineBounds(); const pxPerDay=18;
  state.dependencies.forEach(d=>{
    const pred=state.tasks.find(t=>t.id===d.predecessor_id), succ=state.tasks.find(t=>t.id===d.successor_id); if(!pred||!succ) return;
    const x1 = Math.round((parseDate(pred.end_date)-min)/(1000*60*60*24))*pxPerDay + 12;
    const x2 = Math.round((parseDate(succ.start_date)-min)/(1000*60*60*24))*pxPerDay - 3;
    const y1 = (rowById[pred.id]||0)*37 + 18;
    const y2 = (rowById[succ.id]||0)*37 + 18;
    const mid = Math.max(x1+12, (x1+x2)/2);
    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d', `M ${x1} ${y1} L ${mid} ${y1} L ${mid} ${y2} L ${x2} ${y2}`);
    path.setAttribute('class','dependency-line');
    svg.appendChild(path);
  });
}
function renderSidePanels(){
  const milestones = state.tasks.filter(t=>t.task_type==='milestone').slice(0,6);
  $('#milestonePanel').innerHTML = `<h3>Hitos clave</h3><div class="mini-list">${milestones.map(m=>`<div class="mini-list-item"><span><i class="diamond"></i><b>${safe(m.title)}</b><br><small>${safe(m.end_date)}</small></span><span class="pill ${m.progress===100?'pill-green':''}">${safe(m.status)}</span></div>`).join('') || '<p>No hay hitos.</p>'}</div>`;
  const depTexts = state.dependencies.slice(0,5).map(d=>{
    const a=state.tasks.find(t=>t.id===d.predecessor_id), b=state.tasks.find(t=>t.id===d.successor_id);
    return a&&b ? `<div class="dep-text"><b>${safe(a.title)}</b><br>→ ${safe(b.title)}</div>` : '';
  }).join('');
  $('#dependencyPanel').innerHTML = `<h3>Dependencias críticas</h3>${depTexts || '<p>No hay dependencias configuradas.</p>'}<small>Dependencias totales: ${state.dependencies.length}</small>`;
}
function renderScrum(){
  const activeSprint = state.sprints.find(s=>s.status==='En curso') || state.sprints[0];
  const sprintStories = state.stories.filter(s=>!activeSprint || s.sprint_id===activeSprint.id);
  const total = sprintStories.reduce((a,s)=>a+s.points,0); const done = sprintStories.filter(s=>s.status==='Hecho').reduce((a,s)=>a+s.points,0);
  $('#sprintMetrics').innerHTML = `
    <div class="metric-card"><span>Sprint actual</span><strong>${activeSprint?safe(activeSprint.name):'N/A'}</strong><small>${activeSprint?`${safe(activeSprint.start_date)} → ${safe(activeSprint.end_date)}`:''}</small></div>
    <div class="metric-card"><span>Velocidad</span><strong>${activeSprint?.velocity || 0}</strong><small>puntos promedio</small></div>
    <div class="metric-card"><span>Comprometido</span><strong>${total}</strong><small>story points</small></div>
    <div class="metric-card"><span>Completado</span><strong>${done}</strong><small>${total?Math.round(done/total*100):0}% del sprint</small></div>`;
  renderBurndown(total, done);
  const statuses = state.current_project.parameters?.story_statuses || ['Por hacer','En progreso','Hecho'];
  $('#scrumBoard').innerHTML = statuses.map(st=>{
    const cards = sprintStories.filter(s=>s.status===st).map(s=>storyCard(s,statuses)).join('');
    return `<div class="board-col"><h3>${safe(st)}<span>${sprintStories.filter(s=>s.status===st).length}</span></h3>${cards || '<small>Sin historias</small>'}</div>`;
  }).join('');
}
function storyCard(s,statuses){
  const idx = statuses.indexOf(s.status);
  return `<div class="story-card"><b>${safe(s.title)}</b><p>${safe(s.assignee || 'Sin responsable')} · ${safe(s.priority)}</p><div class="story-footer"><span class="pill">${Number(s.points)} pts</span><span class="move-actions">${idx>0?`<button onclick="moveStory(${Number(s.id)}, ${jsArg(statuses[idx-1])})">←</button>`:''}${idx<statuses.length-1?`<button onclick="moveStory(${Number(s.id)}, ${jsArg(statuses[idx+1])})">→</button>`:''}</span></div></div>`;
}
function renderBurndown(total, done){
  const chart=$('#burndown'); chart.innerHTML=''; const remaining = Math.max(0,total-done);
  const points=[total, Math.round(total*.8), Math.round(total*.62), Math.round(total*.45), remaining];
  const max=Math.max(total,1); const w=240, h=145;
  for(let i=0;i<points.length-1;i++){
    const x1=i*(w/(points.length-1))+18, y1=h-(points[i]/max*h)+8;
    const x2=(i+1)*(w/(points.length-1))+18, y2=h-(points[i+1]/max*h)+8;
    const dx=x2-x1, dy=y2-y1, len=Math.sqrt(dx*dx+dy*dy), ang=Math.atan2(dy,dx)*180/Math.PI;
    chart.insertAdjacentHTML('beforeend', `<div class="chart-line" style="left:${x1}px;top:${y1}px;width:${len}px;transform:rotate(${ang}deg)"></div>`);
    chart.insertAdjacentHTML('beforeend', `<div class="chart-dot" style="left:${x1-4}px;top:${y1-4}px"></div>`);
  }
  const lastX=(points.length-1)*(w/(points.length-1))+18, lastY=h-(points.at(-1)/max*h)+8;
  chart.insertAdjacentHTML('beforeend', `<div class="chart-dot" style="left:${lastX-4}px;top:${lastY-4}px"></div>`);
}
async function moveStory(id,status){
  const s = state.stories.find(x=>x.id===id); if(!s) return;
  await request(`/api/stories/${id}`, {method:'PUT', body:JSON.stringify({...s,status})});
  toast('Historia actualizada'); await load(state.current_project.id);
}
function renderRisks(){
  $('#riskTable').innerHTML = `<div class="table-row header"><span>Riesgo</span><span>Prob.</span><span>Impacto</span><span>Nivel</span><span>Respuesta</span><span>Estado</span></div>` +
  state.risks.map(r=>`<div class="table-row"><b>${safe(r.title)}</b><span>${Number(r.probability)}</span><span>${Number(r.impact)}</span><span class="pill ${r.level==='Alto'?'pill-red':r.level==='Medio'?'pill-amber':'pill-green'}">${safe(r.level)}</span><span>${safe(r.response || '-')}</span><span>${safe(r.status)}</span></div>`).join('');
}
function renderResources(){
  $('#resourceGrid').innerHTML = state.resources.map(r=>`<div class="resource-card"><div class="avatar">${safe(r.name.split(' ').map(x=>x[0]).slice(0,2).join(''))}</div><h3>${safe(r.name)}</h3><p><b>${safe(r.role || 'Rol pendiente')}</b><br>${safe(r.email || '')}</p><span class="pill">Capacidad ${Number(r.capacity)}%</span><div class="capacity-bar"><i style="width:${clamp(r.capacity,0,100)}%"></i></div></div>`).join('') || '<p>No hay recursos.</p>';
}
function renderParameters(){
  const p=state.current_project; const params = p.parameters || state.defaults;
  const phases = (params.phases||[]).join(', '), tStatuses=(params.task_statuses||[]).join(', '), sStatuses=(params.story_statuses||[]).join(', '), methods=(params.execution_methodologies||[]).join(', ');
  $('#parametersForm').innerHTML = `
    <div class="parameter-block"><h3>Datos generales del proyecto</h3><div class="form-grid">
      <label>Nombre<input id="param_name" value="${escapeHtml(p.name)}"></label>
      <label>Project Manager<input id="param_pm" value="${escapeHtml(p.project_manager||'')}"></label>
      <label>Sponsor<input id="param_sponsor" value="${escapeHtml(p.sponsor||'')}"></label>
      <label>Fecha inicio<input id="param_start" type="date" value="${p.start_date}"></label>
      <label>Fecha fin<input id="param_end" type="date" value="${p.end_date}"></label>
      <label>Presupuesto<input id="param_budget" type="number" value="${p.budget||0}"></label>
      <label>Moneda<input id="param_currency" value="${p.currency||'COP'}"></label>
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
      <label>Días laborales<input id="param_working_days" value="${escapeHtml((params.calendar?.working_days||[]).join(', '))}"></label>
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
      <label class="inline-check"><input id="param_cp" type="checkbox" ${params.governance?.critical_path_enabled?'checked':''}> Ruta crítica activa</label>
      <label class="inline-check"><input id="param_budget_control" type="checkbox" ${params.governance?.budget_control_enabled?'checked':''}> Control de presupuesto</label>
      <label class="inline-check"><input id="param_weekly" type="checkbox" ${params.governance?.weekly_status_report?'checked':''}> Reporte semanal</label>
      <label class="inline-check"><input id="param_ai_enabled" type="checkbox" ${params.ai?.enabled?'checked':''}> IA habilitada</label>
      <label>Proveedor IA<input id="param_ai_provider" value="${escapeHtml(params.ai?.provider || 'OpenAI / Azure OpenAI')}"></label>
      <label>Modelo IA<input id="param_ai_model" value="${escapeHtml(params.ai?.model || 'configurable')}"></label>
    </div></div>`;
  $('#param_status').value = p.status;
}
function collectParameters(){
  const split = (v)=> String(v||'').split(',').map(x=>x.trim()).filter(Boolean);
  const params = {
    control_model: $('#param_control').value,
    execution_methodologies: split($('#param_methods').value),
    selected_execution_methodology: $('#param_selected_method').value,
    calendar: {working_days: split($('#param_working_days').value), workday_start: $('#param_work_start').value, workday_end: $('#param_work_end').value, timezone: $('#param_timezone').value},
    phases: split($('#param_phases').value),
    task_statuses: split($('#param_task_statuses').value),
    story_statuses: split($('#param_story_statuses').value),
    sprint: {duration_days: Number($('#param_sprint_days').value || 14), story_point_scale: [1,2,3,5,8,13]},
    risk_matrix: {probability_scale:[1,2,3,4,5], impact_scale:[1,2,3,4,5], medium_threshold:Number($('#param_medium').value||8), high_threshold:Number($('#param_high').value||15)},
    governance: {critical_path_enabled: $('#param_cp').checked, budget_control_enabled: $('#param_budget_control').checked, weekly_status_report: $('#param_weekly').checked, stage_gate_approval: true},
    ai: {enabled: $('#param_ai_enabled').checked, provider: $('#param_ai_provider').value, model: $('#param_ai_model').value, use_project_documents:true, allow_create_tasks:true, allow_create_risks:true}
  };
  return {
    name: $('#param_name').value,
    project_manager: $('#param_pm').value,
    sponsor: $('#param_sponsor').value,
    start_date: $('#param_start').value,
    end_date: $('#param_end').value,
    budget: Number($('#param_budget').value||0),
    currency: $('#param_currency').value,
    status: $('#param_status').value,
    methodology: $('#param_methodology').value,
    parameters: params
  };
}
async function saveParameters(){
  await request(`/api/projects/${state.current_project.id}`, {method:'PUT', body:JSON.stringify(collectParameters())});
  toast('Parámetros guardados'); await load(state.current_project.id);
}
function renderView(view){
  state.view = view;
  $$('.view').forEach(v=>v.classList.add('hidden'));
  const el = $(`#view-${view}`) || $('#view-gantt'); el.classList.remove('hidden');
  $$('.side-item,.top-tab').forEach(b=>b.classList.toggle('active', b.dataset.view===view || (view==='gantt' && ['Plan Maestro','Gantt'].includes(b.textContent.trim()))));
  if(view==='gantt') setTimeout(drawDependencies, 50);
}
function openModal(title, html){ $('#modalTitle').textContent=title; $('#modalBody').innerHTML=html; $('#entityModal').classList.remove('hidden'); }
function closeModal(){ $('#entityModal').classList.add('hidden'); }
function modalActions(submitLabel='Guardar'){ return `<div class="modal-actions"><button class="btn ghost" data-close="modal">Cancelar</button><button class="btn primary" type="submit">${submitLabel}</button></div>`; }
function getPhasesOptions(selected=''){ return (state.current_project.parameters?.phases || ['Inicio','Planeación','Ejecución','Pruebas','Cierre']).map(x=>`<option ${x===selected?'selected':''}>${safe(x)}</option>`).join(''); }
function getTaskOptions(selected=''){ return `<option value="">Sin dependencia</option>`+state.tasks.map(t=>`<option value="${Number(t.id)}" ${t.id===selected?'selected':''}>${safe(t.title)}</option>`).join(''); }
function getSprintOptions(selected){ return `<option value="">Sin sprint</option>`+state.sprints.map(s=>`<option value="${Number(s.id)}" ${s.id===selected?'selected':''}>${safe(s.name)}</option>`).join(''); }
function getResourceNamesOptions(selected=''){ return [''].concat(state.resources.map(r=>r.name)).map(x=>`<option ${x===selected?'selected':''}>${safe(x)}</option>`).join(''); }
function openTaskModal(id=null){
  const t = id ? state.tasks.find(x=>x.id===id) : {project_id:state.current_project.id,title:'',phase:'Ejecución',task_type:'task',start_date:state.current_project.start_date,end_date:state.current_project.start_date,progress:0,owner:'',status:'Pendiente',story_points:0,budget:0,description:'',order_index:state.tasks.length+1};
  openModal(id?'Editar actividad':'Nueva actividad / hito', `<form id="taskForm"><div class="form-grid two">
    <label>Título<input name="title" value="${escapeHtml(t.title)}" required></label>
    <label>Tipo<select name="task_type"><option value="task" ${t.task_type==='task'?'selected':''}>Actividad</option><option value="milestone" ${t.task_type==='milestone'?'selected':''}>Hito</option></select></label>
    <label>Fase<select name="phase">${getPhasesOptions(t.phase)}</select></label>
    <label>Responsable<select name="owner">${getResourceNamesOptions(t.owner)}</select></label>
    <label>Fecha inicio<input name="start_date" type="date" value="${t.start_date}" required></label>
    <label>Fecha fin<input name="end_date" type="date" value="${t.end_date}" required></label>
    <label>Avance %<input name="progress" type="number" min="0" max="100" value="${t.progress||0}"></label>
    <label>Estado<input name="status" value="${escapeHtml(t.status||'Pendiente')}"></label>
    <label>Story points<input name="story_points" type="number" min="0" value="${t.story_points||0}"></label>
    <label>Presupuesto<input name="budget" type="number" min="0" value="${t.budget||0}"></label>
    ${id?'':`<label>Depende de<select name="predecessor_id">${getTaskOptions('')}</select></label>`}
    <label>Orden<input name="order_index" type="number" value="${t.order_index||state.tasks.length+1}"></label>
  </div><label>Descripción<textarea name="description" rows="3">${escapeHtml(t.description||'')}</textarea></label>${modalActions(id?'Actualizar':'Crear')}</form>`);
  $('#taskForm').addEventListener('submit', async e=>{
    e.preventDefault(); const fd=new FormData(e.target); const body=Object.fromEntries(fd.entries());
    body.project_id=state.current_project.id; body.progress=Number(body.progress||0); body.story_points=Number(body.story_points||0); body.budget=Number(body.budget||0); body.order_index=Number(body.order_index||0); if(!body.predecessor_id) delete body.predecessor_id; else body.predecessor_id=Number(body.predecessor_id);
    await request(id?`/api/tasks/${id}`:'/api/tasks', {method:id?'PUT':'POST', body:JSON.stringify(body)}); closeModal(); toast(id?'Actividad actualizada':'Actividad creada'); await load(state.current_project.id);
  });
}
async function removeTask(id){ if(!confirm('¿Eliminar esta actividad y sus dependencias?')) return; await request(`/api/tasks/${id}`, {method:'DELETE'}); toast('Actividad eliminada'); await load(state.current_project.id); }
function openStoryModal(){
  openModal('Nueva historia de usuario', `<form id="storyForm"><div class="form-grid two">
    <label>Título<input name="title" required placeholder="US-27 Nueva funcionalidad"></label>
    <label>Sprint<select name="sprint_id">${getSprintOptions()}</select></label>
    <label>Estado<select name="status"><option>Por hacer</option><option>En progreso</option><option>Hecho</option></select></label>
    <label>Puntos<input name="points" type="number" value="5" min="0"></label>
    <label>Responsable<select name="assignee">${getResourceNamesOptions()}</select></label>
    <label>Prioridad<select name="priority"><option>Alta</option><option selected>Media</option><option>Baja</option></select></label>
  </div>${modalActions('Crear')}</form>`);
  $('#storyForm').addEventListener('submit', async e=>{ e.preventDefault(); const body=Object.fromEntries(new FormData(e.target).entries()); body.project_id=state.current_project.id; body.points=Number(body.points||0); body.sprint_id=body.sprint_id?Number(body.sprint_id):null; await request('/api/stories',{method:'POST',body:JSON.stringify(body)}); closeModal(); toast('Historia creada'); await load(state.current_project.id); });
}
function openRiskModal(){
  openModal('Nuevo riesgo', `<form id="riskForm"><div class="form-grid two">
    <label>Riesgo<input name="title" required></label>
    <label>Responsable<select name="owner">${getResourceNamesOptions()}</select></label>
    <label>Probabilidad 1-5<input name="probability" type="number" min="1" max="5" value="3"></label>
    <label>Impacto 1-5<input name="impact" type="number" min="1" max="5" value="3"></label>
    <label>Estado<select name="status"><option>Abierto</option><option>Mitigado</option><option>Cerrado</option></select></label>
  </div><label>Respuesta<textarea name="response" rows="3"></textarea></label>${modalActions('Crear')}</form>`);
  $('#riskForm').addEventListener('submit', async e=>{ e.preventDefault(); const body=Object.fromEntries(new FormData(e.target).entries()); body.project_id=state.current_project.id; body.probability=Number(body.probability||1); body.impact=Number(body.impact||1); await request('/api/risks',{method:'POST',body:JSON.stringify(body)}); closeModal(); toast('Riesgo creado'); await load(state.current_project.id); });
}
function openResourceModal(){
  openModal('Nuevo recurso', `<form id="resourceForm"><div class="form-grid two">
    <label>Nombre<input name="name" required></label>
    <label>Rol<input name="role"></label>
    <label>Email<input name="email" type="email"></label>
    <label>Capacidad %<input name="capacity" type="number" min="0" max="100" value="100"></label>
  </div>${modalActions('Crear')}</form>`);
  $('#resourceForm').addEventListener('submit', async e=>{ e.preventDefault(); const body=Object.fromEntries(new FormData(e.target).entries()); body.project_id=state.current_project.id; body.capacity=Number(body.capacity||100); await request('/api/resources',{method:'POST',body:JSON.stringify(body)}); closeModal(); toast('Recurso creado'); await load(state.current_project.id); });
}
function openNewProjectModal(){
  const today = iso(new Date()); const end = new Date(); end.setDate(end.getDate()+90);
  openModal('Nuevo proyecto parametrizable', `<form id="projectForm"><div class="form-grid two">
    <label>Nombre<input name="name" required value="Nuevo proyecto"></label>
    <label>Project Manager<input name="project_manager" value=""></label>
    <label>Sponsor<input name="sponsor" value=""></label>
    <label>Fecha inicio<input name="start_date" type="date" value="${today}"></label>
    <label>Fecha fin<input name="end_date" type="date" value="${iso(end)}"></label>
    <label>Presupuesto<input name="budget" type="number" value="0"></label>
    <label>Moneda<input name="currency" value="COP"></label>
    <label>Metodología<select name="methodology"><option>Híbrida PMP + Scrum</option><option>Tradicional PMP</option><option>Ágil Scrum</option><option>Híbrida personalizada</option></select></label>
  </div><label>Descripción<textarea name="description" rows="3">Proyecto creado desde Proyecta360.</textarea></label>${modalActions('Crear proyecto')}</form>`);
  $('#projectForm').addEventListener('submit', async e=>{ e.preventDefault(); const body=Object.fromEntries(new FormData(e.target).entries()); body.budget=Number(body.budget||0); body.status='Planeado'; body.parameters=state.defaults; const created=await request('/api/projects',{method:'POST', body:JSON.stringify(body)}); closeModal(); toast('Proyecto creado'); await load(created.id); renderView('parameters'); });
}
async function aiGeneratePlan(){
  const body = {project_id:state.current_project.id, objective:$('#aiObjective').value, execution_methodology:$('#aiMethodology').value, horizon_weeks:Number($('#aiWeeks').value||12), create_records:true};
  const res = await request('/api/ai/generate-plan',{method:'POST',body:JSON.stringify(body)});
  $('#aiOutput').textContent = `${res.message}\n\nActividades generadas:\n` + res.generated_tasks.map((t,i)=>`${i+1}. ${t.title} | ${t.phase} | ${t.start_date} → ${t.end_date}`).join('\n');
  toast('Plan generado y agregado al Gantt'); await load(state.current_project.id); renderView('ai');
}
async function aiGenerateReport(){
  const res = await request('/api/ai/report',{method:'POST',body:JSON.stringify({project_id:state.current_project.id,audience:'Comité Directivo'})});
  $('#aiOutput').textContent = res.report;
  renderView('ai');
}
function bindEvents(){
  $$('.side-item,.top-tab').forEach(b=>b.addEventListener('click',()=>renderView(b.dataset.view || 'gantt')));
  $('#projectSelector').addEventListener('change', e=>load(Number(e.target.value)));
  $('#btnReload').addEventListener('click',()=>load(state.current_project.id));
  $('#btnAddTask').addEventListener('click',()=>openTaskModal());
  $('#btnAiPlan').addEventListener('click',()=>{renderView('ai'); $('#aiObjective').focus();});
  $('#btnOpenParameters').addEventListener('click',()=>renderView('parameters'));
  $('#btnSaveParametersInline').addEventListener('click',saveParameters);
  $('#btnNewProject').addEventListener('click',openNewProjectModal);
  $('#btnAddStory').addEventListener('click',openStoryModal);
  $('#btnAddRisk').addEventListener('click',openRiskModal);
  $('#btnAddResource').addEventListener('click',openResourceModal);
  $('#btnGeneratePlan').addEventListener('click',aiGeneratePlan);
  $('#btnGenerateReport').addEventListener('click',aiGenerateReport);
  $$('[data-close="modal"]').forEach(x=>x.addEventListener('click',closeModal));
  $('#entityModal').addEventListener('click',e=>{ if(e.target.dataset.close==='modal') closeModal(); });
  window.addEventListener('resize',()=> state.view==='gantt' && drawDependencies());
}

window.openTaskModal = openTaskModal;
window.removeTask = removeTask;
window.moveStory = moveStory;
window.load = load;

bindEvents();
load().catch(err=>{ console.error(err); toast(err.message); });
