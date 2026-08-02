const API = '';
const state = {
  projects: [], portfolio: [], current_project: null, tasks: [], dependencies: [], sprints: [], stories: [], risks: [], resources: [], components: [], deliverables: [], evidences: [], history: [], conversation_threads: [], conversation_messages: [], active_thread_id: null, selected_task_id: null, gantt_scale: 'days', gantt_zoom: 1, gantt_fit_px: null, gantt_manual_zoom: false, intelligence: {}, metrics: {}, defaults: {}, current_user: null, view: 'gantt'
};
const AUTH_TOKEN_KEY = 'proyecta360_token';

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const fmt = new Intl.NumberFormat('es-CO');
const slug = (value='') => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '') || 'custom';
const knownPhase = (phase='') => ['Inicio','Planeacion','Ejecucion','Pruebas','Cierre'].includes(slug(phase)) ? slug(phase) : 'custom';
const barClass = (phase='') => `bar-${knownPhase(phase)}`;
const parseDate = (d) => new Date(`${d}T00:00:00`);
const iso = (d) => d.toISOString().slice(0,10);
const daysBetween = (a,b) => Math.round((parseDate(b)-parseDate(a))/(1000*60*60*24));
const clamp = (v,min,max) => Math.max(min, Math.min(max, v));
const fmtDate = (value) => value ? parseDate(value).toLocaleDateString('es-CO',{day:'numeric',month:'short',year:'numeric'}) : '-';
const compactDate = (value) => value ? String(value).slice(0,10) : '-';
const ganttBasePxPerDay = () => ({days:18,weeks:7,months:2.6}[state.gantt_scale] || 18);
const ganttPxPerDay = () => state.gantt_fit_px || (ganttBasePxPerDay() * state.gantt_zoom);
const zoomLevels = [0.55,0.75,1,1.25,1.55,1.9];
const ganttRowHeight = 40;
function escapeHtml(str=''){ return String(str).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#39;"); }
const safe = escapeHtml;
function toast(msg){ const el=$('#toast'); el.textContent=msg; el.classList.remove('hidden'); setTimeout(()=>el.classList.add('hidden'), 3300); }
function on(sel, event, handler){ const el = $(sel); if(el) el.addEventListener(event, handler); }

function scrubCredentialQuery(){
  const url = new URL(window.location.href);
  if(url.searchParams.has('email') || url.searchParams.has('password')){
    url.searchParams.delete('email');
    url.searchParams.delete('password');
    window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
  }
}

async function request(path, options={}){
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const isForm = options.body instanceof FormData;
  const headers = {...(isForm ? {} : {'Content-Type':'application/json'}), ...(options.headers || {})};
  if(token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {...options, headers});
  if(!res.ok){
    let detail = 'Error en la operaci?n';
    try{ detail = (await res.json()).detail || detail; }catch(e){}
    if(res.status === 401){
      localStorage.removeItem(AUTH_TOKEN_KEY);
      state.current_user = null;
      showAuthGate();
    }
    throw new Error(detail);
  }
  return res.json();
}
async function load(projectId){
  if(!localStorage.getItem(AUTH_TOKEN_KEY)){ showAuthGate(); return; }
  const query = projectId ? `?project_id=${projectId}` : '';
  Object.assign(state, await request(`/api/bootstrap${query}`));
  showApp();
  renderAll();
}

function showAuthGate(){
  $('#authGate')?.classList.remove('hidden');
  $('#appShell')?.classList.add('hidden');
  closeModal();
}

function showApp(){
  $('#authGate')?.classList.add('hidden');
  $('#appShell')?.classList.remove('hidden');
}

function renderAll(){
  renderHeader(); renderKpis(); renderPortfolio(); renderGantt(); renderSidePanels(); renderScrum(); renderRisks(); renderResources(); renderConversations(); renderKnowledge(); renderParameters(); renderView(state.view);
}
function renderHeader(){
  const p = state.current_project; if(!p) return;
  $('#projectTitle').textContent = p.name;
  $('#projectDescription').textContent = p.description || 'Sin descripción registrada.';
  $('#projectMethodology').textContent = p.methodology;
  $('#projectStatus').textContent = p.status;
  $('#projectDates').textContent = `${p.start_date} → ${p.end_date}`;
  renderAuthState();
  const sel = $('#projectSelector');
  sel.innerHTML = state.projects.map(pr => `<option value="${Number(pr.id)}" ${pr.id===p.id?'selected':''}>${safe(pr.name)}</option>`).join('');
}
function renderAuthState(){
  const user = state.current_user;
  const label = $('#authUserLabel');
  if(label) label.textContent = user ? `${user.name} · ${user.role}` : 'Sin sesión';
  $('#btnLogout')?.classList.toggle('hidden', !user);
  $('#btnLogin')?.classList.toggle('hidden', !!user);
}

function renderKpis(){
  const m=state.metrics || {}, p=state.current_project || {};
  const progress = Number(m.progress || 0);
  const spent = Math.round(m.spent || 0);
  const budget = Math.round(m.budget || 0);
  const finalDate = p.end_date ? fmtDate(p.end_date) : '-';
  const routeLabel = Number(m.critical_path_tasks || 0) > 0 ? 'Activa' : 'Sin ruta';
  $('#kpiStrip').innerHTML = `
    <div class="kpi kpi-progress"><div class="mini-donut" style="--value:${progress}"><b>${progress}%</b></div><div><span>Avance general</span><strong>${progress}%</strong><small>Completado</small></div></div>
    <div class="kpi"><i class="kpi-icon blue">▣</i><div><span>Fecha fin calculada</span><strong>${safe(finalDate)}</strong><small>Segun plan actual</small></div></div>
    <div class="kpi"><i class="kpi-icon amber">△</i><div><span>Riesgos abiertos</span><strong>${m.open_risks || 0}</strong><small>${m.high_risks || 0} altos</small></div></div>
    <div class="kpi"><i class="kpi-icon red">⌁</i><div><span>Ruta critica</span><strong>${safe(routeLabel)}</strong><small>${m.critical_path_tasks || 0} tareas</small></div></div>
    <div class="kpi"><i class="kpi-icon green">$</i><div><span>Presupuesto ejecutado</span><strong>$ ${fmt.format(spent)}</strong><small>de $ ${fmt.format(budget)} ${safe(p.currency || '')}</small></div></div>`;
  const donut = $('#progressDonut'); if(donut){ donut.style.setProperty('--value', progress); donut.querySelector('span').textContent = `${progress}%`; }
}
function renderPortfolio(){
  const rows = state.portfolio?.length ? state.portfolio : state.projects.map(p=>({project_id:p.id,name:p.name,project_manager:p.project_manager,methodology:p.methodology,status:p.status,start_date:p.start_date,end_date:p.end_date,budget:p.budget,currency:p.currency,progress:0,spent:0,open_risks:0,critical_path_tasks:0,health:'N/A'}));
  $('#portfolioGrid').className = 'portfolio-table-wrap';
  $('#portfolioGrid').innerHTML = `<div class="portfolio-toolbar"><strong>${rows.length} proyectos</strong><span>Filtra por cualquier columna y abre el proyecto desde la fila.</span></div>
  <div class="portfolio-table">
    <div class="portfolio-row portfolio-filter">
      ${['Proyecto','Project Manager','Metodología','Estado','Inicio','Fin calc.','Avance','Presupuesto ejec.','Moneda','Riesgos','Ruta crítica',''].map((h,i)=> i<10?`<input data-portfolio-filter="${i}" placeholder="${h}">`:'<span></span>').join('')}
    </div>
    <div class="portfolio-row portfolio-head"><span>Proyecto</span><span>Project Manager</span><span>Metodología</span><span>Estado</span><span>Inicio</span><span>Fin calc.</span><span>Avance</span><span>Presupuesto ejec.</span><span>Moneda</span><span>Riesgos</span><span>Ruta crítica</span><span>Abrir</span></div>
    <div id="portfolioRows">${portfolioRowsHtml(rows)}</div>
  </div>`;
  $$('[data-portfolio-filter]').forEach(input=>input.addEventListener('input',()=>filterPortfolioRows(rows)));
}
function portfolioRowsHtml(rows){
  return rows.map(r=>`<div class="portfolio-row portfolio-data" data-search="${safe([r.name,r.project_manager,r.methodology,r.status,r.start_date,r.end_date,r.progress,r.spent,r.currency,r.open_risks,r.critical_path_tasks].join(' ').toLowerCase())}">
    <b>${safe(r.name)}</b><span>${safe(r.project_manager || 'N/A')}</span><span>${safe(r.methodology)}</span><span><i class="status-dot"></i>${safe(r.status)}</span><span>${safe(r.start_date)}</span><span>${safe(r.end_date)}</span><span>${Number(r.progress||0)}%</span><span>$${fmt.format(Math.round(r.spent||0))}</span><span>${safe(r.currency || 'COP')}</span><span>${Number(r.open_risks||0)}</span><span>${Number(r.critical_path_tasks||0)}</span><span><button class="btn tiny" data-action="open-project" data-id="${Number(r.project_id || r.id)}">Abrir</button></span>
  </div>`).join('');
}
function filterPortfolioRows(rows){
  const filters = $$('[data-portfolio-filter]').map(x=>x.value.trim().toLowerCase());
  $$('#portfolioRows .portfolio-data').forEach(row=>{
    const cells=[...row.children].map(c=>c.textContent.toLowerCase());
    const ok=filters.every((f,i)=>!f || (cells[i]||'').includes(f));
    row.style.display=ok?'grid':'none';
  });
}
function timelineBounds(){
  const p = state.current_project;
  let min = parseDate(p.start_date), max = parseDate(p.end_date);
  state.tasks.forEach(t=>{ min = parseDate(t.start_date) < min ? parseDate(t.start_date) : min; max = parseDate(t.end_date) > max ? parseDate(t.end_date) : max; });
  min = new Date(min.getFullYear(), min.getMonth(), 1);
  max = new Date(max.getFullYear(), max.getMonth() + 1, 0);
  return {min, max, total: Math.max(1, Math.round((max-min)/(1000*60*60*24)))};
}
function updateZoomControl(){
  const controls = $('#ganttZoomControls');
  if(!controls) return;
  const range = $('#ganttZoomRange');
  const min = Number(range?.min || 0.55);
  const max = Number(range?.max || 1.9);
  const value = state.gantt_fit_px ? max : state.gantt_zoom;
  const pct = Math.round((value - min) / (max - min) * 100);
  controls.style.setProperty('--zoom-pos', `${pct}%`);
  controls.classList.toggle('fit', Boolean(state.gantt_fit_px));
  if(range && Number(range.value) !== Number(value.toFixed(2))) range.value = value.toFixed(2);
}
function fitGanttToViewport({render=true}={}){
  const wrap = $('.timeline-wrap');
  const {total} = timelineBounds();
  const available = Math.max(260, (wrap?.clientWidth || 720) - 2);
  state.gantt_fit_px = clamp(available / Math.max(1,total + 1), 1.1, 22);
  updateZoomControl();
  if(render) renderGantt();
}
function renderGantt(){
  const tasks = visibleTasks();
  const totalTasks = state.tasks.filter(t=>t.task_type !== 'summary' && !hasChildren(t.id)).length;
  const summaries = state.tasks.filter(t=>t.task_type === 'summary' || hasChildren(t.id)).length;
  const milestones = state.tasks.filter(t=>t.task_type === 'milestone').length;
  $('#ganttSummary') && ($('#ganttSummary').textContent = `${state.tasks.length} tareas (${summaries} resumen, ${totalTasks} tareas, ${milestones} hitos)`);
  $('#taskRows').innerHTML = tasks.map((t,idx)=>{
    const level = Number(t.outline_level || 0);
    const isSummary = t.task_type === 'summary' || hasChildren(t.id);
    const canIndent = idx > 0;
    const canOutdent = Boolean(t.parent_id);
    const selected = Number(state.selected_task_id) === Number(t.id);
    const expander = hasChildren(t.id) ? `<button class="tree-toggle" data-action="toggle-task" data-id="${Number(t.id)}">${Number(t.is_expanded)===0?'▸':'▾'}</button>` : '<span class="tree-space"></span>';
    const icon = t.task_type==='milestone' ? '<i class="milestone-ico"></i>' : isSummary ? '<i class="summary-ico"></i>' : '<i class="task-ico"></i>';
    const preds = dependencyTextForTask(t.id);
    const indentButton = `<button class="icon-btn" ${canIndent ? `data-action="indent-task" data-id="${Number(t.id)}" title="Aplicar sangria"` : 'disabled title="No hay tarea anterior para aplicar sangria"'}>↷</button>`;
    const outdentButton = `<button class="icon-btn" ${canOutdent ? `data-action="outdent-task" data-id="${Number(t.id)}" title="Quitar sangria"` : 'disabled title="La tarea ya esta en el nivel principal"'}>↶</button>`;
    return `<div class="task-row ms-task-row ${isSummary?'summary-row':''} ${selected?'selected':''}" data-action="select-task" data-id="${Number(t.id)}">
      <span>${t.order_index || idx+1}</span>
      <span class="task-title ms-task-title" style="--level:${level}">${expander}${icon}<b title="${safe(t.title)}">${safe(t.title)}</b></span>
      <span>${Number(t.duration_days ?? Math.max(0, daysBetween(t.start_date,t.end_date)+1))}d</span>
      <span class="date-cell">${compactDate(t.start_date)}</span>
      <span class="date-cell">${compactDate(t.end_date)}</span>
      <span title="${safe(preds)}">${safe(preds || '—')}</span>
      <span title="${safe(t.owner)}">${safe(t.owner || '—')}</span>
      <span class="progress-cell"><b>${Number(t.progress||0)}%</b><div class="progress-mini"><i style="width:${clamp(t.progress,0,100)}%"></i></div></span>
      <span class="row-actions">${indentButton}${outdentButton}<button class="icon-btn" data-action="edit-task" data-id="${Number(t.id)}" title="Editar">✎</button><button class="icon-btn" data-action="remove-task" data-id="${Number(t.id)}" title="Borrar">×</button></span>
    </div>`;
  }).join('');

  const {min,total} = timelineBounds();
  const pxPerDay = ganttPxPerDay();
  const timelineViewport = $('.timeline-wrap')?.clientWidth || 0;
  const width = Math.max(timelineViewport, (total + 1) * pxPerDay);
  const header = $('#timelineHeader');
  const grid = $('#ganttGrid');
  header.style.width = `${width}px`;
  grid.style.width = `${width}px`;
  grid.style.height = `${Math.max(594, tasks.length*ganttRowHeight)}px`;
  $$('#ganttScaleControl [data-scale]').forEach(btn=>btn.classList.toggle('active', btn.dataset.scale === state.gantt_scale));
  updateZoomControl();
  header.innerHTML = '<div class="timeline-months"></div><div class="timeline-weeks"></div>';
  const monthRow = header.querySelector('.timeline-months');
  const weekRow = header.querySelector('.timeline-weeks');
  let monthCursor = new Date(min.getFullYear(), min.getMonth(), 1);
  while(monthCursor <= new Date(min.getTime() + total*86400000)){
    const monthStart = Math.max(0, Math.round((monthCursor - min)/86400000) * pxPerDay);
    const nextMonth = new Date(monthCursor.getFullYear(), monthCursor.getMonth()+1, 1);
    const monthEnd = Math.min(width, Math.round((nextMonth - min)/86400000) * pxPerDay);
    monthRow.insertAdjacentHTML('beforeend', `<div class="month-cell" style="left:${monthStart}px;width:${Math.max(60,monthEnd-monthStart)}px">${monthCursor.toLocaleDateString('es-CO',{month:'short',year:'numeric'})}</div>`);
    monthCursor = nextMonth;
  }
  const stepDays = state.gantt_scale === 'months' ? 30 : 7;
  const minorWidth = Math.max(54, stepDays * pxPerDay);
  for(let day=0; day<=total; day+=stepDays){
    const d = new Date(min); d.setDate(min.getDate()+day);
    const label = state.gantt_scale === 'months'
      ? d.toLocaleDateString('es-CO',{month:'short'})
      : d.toLocaleDateString('es-CO',{day:'numeric',month:'short'});
    weekRow.insertAdjacentHTML('beforeend', `<div class="week-cell" style="left:${day*pxPerDay}px;width:${minorWidth}px">${label}</div>`);
  }
  grid.innerHTML = '';
  for(let day=0; day<=total; day+=stepDays) grid.insertAdjacentHTML('beforeend', `<div class="grid-col" style="left:${day*pxPerDay}px;width:${minorWidth}px"></div>`);
  tasks.forEach((t,idx)=>{
    grid.insertAdjacentHTML('beforeend', `<div class="gantt-row-line ${Number(state.selected_task_id)===Number(t.id)?'selected':''}" style="top:${idx*ganttRowHeight}px"></div>`);
    const start = Math.max(0, Math.round((parseDate(t.start_date)-min)/86400000)*pxPerDay);
    const duration = Math.max(t.task_type==='milestone'?1:2, (daysBetween(t.start_date,t.end_date)+1)*pxPerDay);
    const top = idx*ganttRowHeight + 8;
    const isSummary = t.task_type === 'summary' || hasChildren(t.id);
    if(t.task_type === 'milestone'){
      grid.insertAdjacentHTML('beforeend', `<div class="milestone" data-task="${Number(t.id)}" title="${safe(t.title)}" style="left:${start}px;top:${top+1}px"></div>`);
    }else{
      const compact = duration < 72;
      const label = compact ? '' : `<span>${safe(t.title)}</span>`;
      grid.insertAdjacentHTML('beforeend', `<div class="bar ${isSummary?'bar-summary':barClass(t.phase)} ${compact?'bar-compact':''}" data-task="${Number(t.id)}" title="${safe(t.title)}" style="left:${start}px;top:${top}px;width:${duration}px"><i class="bar-fill" style="width:${clamp(t.progress,0,100)}%"></i>${label}</div>`);
    }
  });
  const todayX = Math.round((new Date(new Date().toDateString())-min)/86400000)*pxPerDay;
  if(todayX >=0 && todayX <= width){ grid.insertAdjacentHTML('beforeend', `<div class="today-line" style="left:${todayX}px"></div>`); }
  setTimeout(drawDependencies, 50);
}
function drawDependencies(){
  const svg = $('#dependencySvg'); const grid=$('#ganttGrid');
  const tasks = visibleTasks();
  const rowById = Object.fromEntries(tasks.map((t,i)=>[t.id,i]));
  svg.setAttribute('width', grid.scrollWidth); svg.setAttribute('height', grid.scrollHeight); svg.innerHTML = `<defs><marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#2563eb"></polygon></marker></defs>`;
  const {min} = timelineBounds(); const pxPerDay=ganttPxPerDay();
  state.dependencies.forEach(d=>{
    const pred=state.tasks.find(t=>t.id===d.predecessor_id), succ=state.tasks.find(t=>t.id===d.successor_id); if(!pred||!succ) return;
    if(rowById[pred.id] === undefined || rowById[succ.id] === undefined) return;
    const type=(d.dependency_type||'FS').toUpperCase();
    const predAnchor = (type==='SS'||type==='SF') ? pred.start_date : pred.end_date;
    const succAnchor = (type==='FF'||type==='SF') ? succ.end_date : succ.start_date;
    const x1 = Math.round((parseDate(predAnchor)-min)/(1000*60*60*24))*pxPerDay + ((type==='SS'||type==='SF')?0:12);
    const x2 = Math.round((parseDate(succAnchor)-min)/(1000*60*60*24))*pxPerDay - 3;
    const y1 = (rowById[pred.id]||0)*ganttRowHeight + 18;
    const y2 = (rowById[succ.id]||0)*ganttRowHeight + 18;
    const mid = Math.max(x1+12, (x1+x2)/2);
    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d', `M ${x1} ${y1} L ${mid} ${y1} L ${mid} ${y2} L ${x2} ${y2}`);
    path.setAttribute('class','dependency-line');
    path.setAttribute('marker-end','url(#arrowhead)');
    svg.appendChild(path);
  });
}
async function indentTask(id){ await request(`/api/tasks/${id}/indent`, {method:'POST'}); toast('Sangría aplicada'); await load(state.current_project.id); }
async function outdentTask(id){ await request(`/api/tasks/${id}/outdent`, {method:'POST'}); toast('Sangría removida'); await load(state.current_project.id); }
async function toggleTask(id){ await request(`/api/tasks/${id}/toggle`, {method:'POST'}); await load(state.current_project.id); }
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
  return `<div class="story-card"><b>${safe(s.title)}</b><p>${safe(s.assignee || 'Sin responsable')} · ${safe(s.priority)}</p><div class="story-footer"><span class="pill">${Number(s.points)} pts</span><span class="move-actions">${idx>0?`<button data-action="move-story" data-id="${Number(s.id)}" data-status="${safe(statuses[idx-1])}">←</button>`:''}${idx<statuses.length-1?`<button data-action="move-story" data-id="${Number(s.id)}" data-status="${safe(statuses[idx+1])}">→</button>`:''}</span></div></div>`;
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
  $('#riskTable').innerHTML = `<div class="table-row risk-row header"><span>Riesgo</span><span>Prob.</span><span>Impacto</span><span>Nivel</span><span>Mitigación</span><span>Contingencia</span><span>Estado</span></div>` +
  state.risks.map(r=>`<div class="table-row risk-row"><b>${safe(r.title)}</b><span>${Number(r.probability)}</span><span>${Number(r.impact)}</span><span class="pill ${r.level==='Alto'?'pill-red':r.level==='Medio'?'pill-amber':'pill-green'}">${safe(r.level)}</span><span>${safe(r.mitigation_plan || r.response || '-')}</span><span>${safe(r.contingency_plan || '-')}</span><span>${safe(r.status)}</span></div>`).join('');
}
function renderResources(){
  $('#resourceGrid').innerHTML = state.resources.map(r=>`<div class="resource-card"><div class="avatar">${safe(r.name.split(' ').map(x=>x[0]).slice(0,2).join(''))}</div><h3>${safe(r.name)}</h3><p><b>${safe(r.role || 'Rol pendiente')}</b><br>${safe(r.email || '')}</p><span class="pill">Capacidad ${Number(r.capacity)}%</span><div class="capacity-bar"><i style="width:${clamp(r.capacity,0,100)}%"></i></div></div>`).join('') || '<p>No hay recursos.</p>';
}
function contextName(type, id){
  if(!id || type === 'Proyecto') return 'Proyecto';
  const maps = {Componente: state.components, Actividad: state.tasks, Riesgo: state.risks, Entregable: state.deliverables};
  const fields = {Componente: 'name', Actividad: 'title', Riesgo: 'title', Entregable: 'name'};
  const item = (maps[type] || []).find(x=>x.id===id);
  return item ? item[fields[type]] : type;
}
function activeThread(){
  if(!state.active_thread_id && state.conversation_threads.length) state.active_thread_id = state.conversation_threads[0].id;
  return state.conversation_threads.find(t=>t.id===state.active_thread_id);
}
function renderConversations(){
  const thread = activeThread();
  $('#threadList').innerHTML = state.conversation_threads.map(t=>{
    const count = state.conversation_messages.filter(m=>m.thread_id===t.id).length;
    return `<button class="thread-item ${t.id===state.active_thread_id?'active':''}" data-action="select-thread" data-id="${Number(t.id)}">
      <b>${safe(t.title)}</b>
      <span>${safe(t.context_type)} · ${safe(contextName(t.context_type, t.context_id))}</span>
      <small>${safe(t.category)} · ${count} mensajes</small>
    </button>`;
  }).join('') || '<p>No hay conversaciones.</p>';
  $('#messageAuthor').innerHTML = getResourceNamesOptions(state.current_project?.project_manager || '');
  if(!thread){
    $('#activeThreadTitle').textContent = 'Selecciona una conversacion';
    $('#activeThreadMeta').textContent = 'Centraliza acuerdos, bloqueos y decisiones del equipo.';
    $('#activeThreadCategory').textContent = 'Seguimiento';
    $('#messageList').innerHTML = '<p>No hay mensajes.</p>';
    return;
  }
  $('#activeThreadTitle').textContent = thread.title;
  $('#activeThreadMeta').textContent = `${thread.context_type} · ${contextName(thread.context_type, thread.context_id)} · ${thread.status}`;
  $('#activeThreadCategory').textContent = thread.category;
  const messages = state.conversation_messages.filter(m=>m.thread_id===thread.id);
  $('#messageList').innerHTML = messages.map(m=>`<div class="message-item ${m.message_type==='Decision'||m.message_type==='Acuerdo'?'message-decision':m.message_type==='Bloqueo'?'message-blocker':''}">
    <div><b>${safe(m.author || 'Equipo')}</b><span class="pill">${safe(m.message_type)}</span></div>
    <p>${safe(m.message)}</p>
    <small>${safe(m.created_at || '')}${m.mentions?` · ${safe(m.mentions)}`:''}${m.evidence_url?` · <a href="${safe(m.evidence_url)}" target="_blank">Evidencia</a>`:''}</small>
  </div>`).join('') || '<p>Sin mensajes todavia.</p>';
}
function componentName(id){
  const c = state.components.find(x=>x.id===id);
  return c ? c.name : 'Sin componente';
}
function renderKnowledge(){
  const intel = state.intelligence || {};
  $('#componentGrid').innerHTML = state.components.map(c=>`<div class="component-card">
    <div class="component-head"><h3>${safe(c.name)}</h3><span class="pill pill-blue">${safe(c.methodology)}</span></div>
    <p>${safe(c.objective || 'Objetivo pendiente')}</p>
    <small>${safe(c.owner || 'Sin responsable')}</small>
    <div class="capacity-bar"><i style="width:${clamp(c.progress || 0,0,100)}%"></i></div>
  </div>`).join('') || '<p>No hay componentes.</p>';
  $('#deliverableTable').innerHTML = `<div class="knowledge-row header"><span>Producto</span><span>Componente</span><span>Estado</span><span>Fecha</span><span>Evidencia</span></div>` +
    state.deliverables.map(d=>`<div class="knowledge-row"><b>${safe(d.name)}<small>${safe(d.deliverable_type)}</small></b><span>${safe(componentName(d.component_id))}</span><span class="pill ${d.status==='Aprobado'?'pill-green':d.status==='En progreso'?'pill-blue':'pill-amber'}">${safe(d.status)}</span><span>${safe(d.due_date || '-')}</span><span>${d.evidence_url?`<a class="evidence-link" href="${safe(d.evidence_url)}" target="_blank">Abrir</a>`:'-'}</span></div>`).join('');
  const evidenceEl = $('#evidenceTable');
  if(evidenceEl){
    evidenceEl.innerHTML = `<div class="knowledge-row header"><span>Archivo</span><span>Asociado a</span><span>Cargado por</span><span>Tamaño</span><span>Descarga</span></div>` +
      (state.evidences || []).map(ev=>`<div class="knowledge-row"><b>${safe(ev.original_filename)}<small>${safe(ev.description || 'Sin descripción')}</small></b><span>${safe(ev.entity_type)} ${ev.entity_id || ''}</span><span>${safe(ev.uploaded_by || 'Sistema')}</span><span>${fmt.format(Number(ev.size_bytes || 0))} bytes</span><span><a class="evidence-link" href="/api/evidences/${Number(ev.id)}/download" target="_blank">Descargar</a></span></div>`).join('') || '<p>No hay evidencias cargadas.</p>';
  }
  $('#intelligencePanel').innerHTML = `
    <div class="intelligence-status"><span>Estado</span><strong>${safe(intel.status || state.metrics.health || 'N/A')}</strong></div>
    <div class="insight-block"><h3>Riesgos detectados</h3>${(intel.detected_risks||[]).slice(0,3).map(r=>`<p>${safe(r.title)} <span class="pill ${r.level==='Alto'?'pill-red':'pill-amber'}">${safe(r.level)}</span></p>`).join('') || '<p>Sin riesgos abiertos.</p>'}</div>
    <div class="insight-block"><h3>Hitos comprometidos</h3>${(intel.compromised_milestones||[]).slice(0,3).map(m=>`<p>${safe(m.title)} · ${safe(m.end_date)}</p>`).join('') || '<p>Sin hitos comprometidos.</p>'}</div>
    <div class="insight-block"><h3>Recomendaciones</h3>${(intel.recommendations||[]).map(x=>`<p>${safe(x)}</p>`).join('')}</div>`;
  $('#historyList').innerHTML = state.history.map(h=>`<div class="history-item"><b>${safe(h.action)} · ${safe(h.entity_type)}</b><span>${safe(h.entity_name)}</span><small>${safe(h.created_at || '')} · ${safe(h.notes || '')}</small></div>`).join('') || '<p>Sin historial.</p>';
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
    ai: {enabled: $('#param_ai_enabled').checked, model: $('#param_ai_model').value, use_project_documents:true, allow_create_tasks:true, allow_create_risks:true}
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
  $('#kpiStrip')?.classList.toggle('hidden', view === 'portfolio');
  $$('.side-item,.top-tab').forEach(b=>b.classList.toggle('active', b.dataset.view===view || (view==='gantt' && ['Plan Maestro','Gantt'].includes(b.textContent.trim()))));
  if(view==='gantt') setTimeout(drawDependencies, 50);
  if(view==='ai'){
    setAiTab('analysis');
    setTimeout(()=>loadAiSettings(), 50);
  }
  if(view==='parameters') setTimeout(()=>loadAiSettings(), 50);
}
function selectThread(id){
  state.active_thread_id = id;
  renderConversations();
}
function openModal(title, html){
  $('#modalTitle').textContent=title;
  $('#modalBody').innerHTML=html;
  const modal = $('#entityModal');
  modal.style.display = 'grid';
  modal.classList.remove('hidden');
}
function closeModal(){
  const modal = $('#entityModal');
  if(!modal) return;
  modal.classList.add('hidden');
  modal.style.display = 'none';
  $('#modalBody').innerHTML = '';
}
document.addEventListener('click', e=>{
  if(e.target.closest?.('[data-close="modal"]')){
    e.preventDefault();
    e.stopPropagation();
    closeModal();
  }
}, true);
function modalActions(submitLabel='Guardar'){ return `<div class="modal-actions"><button class="btn ghost" type="button" data-close="modal">Cancelar</button><button class="btn primary" type="submit">${submitLabel}</button></div>`; }
function getPhasesOptions(selected=''){ return (state.current_project.parameters?.phases || ['Inicio','Planeación','Ejecución','Pruebas','Cierre']).map(x=>`<option ${x===selected?'selected':''}>${safe(x)}</option>`).join(''); }
function getTaskOptions(selected='', excludedId=null){
  return `<option value="">Sin dependencia</option>`+state.tasks
    .filter(t=>Number(t.id)!==Number(excludedId || 0))
    .map(t=>`<option value="${Number(t.id)}" ${Number(t.id)===Number(selected)?'selected':''}>${safe(t.title)}</option>`)
    .join('');
}
function getSprintOptions(selected){ return `<option value="">Sin sprint</option>`+state.sprints.map(s=>`<option value="${Number(s.id)}" ${s.id===selected?'selected':''}>${safe(s.name)}</option>`).join(''); }
function getResourceNamesOptions(selected=''){ return [''].concat(state.resources.map(r=>r.name)).map(x=>`<option ${x===selected?'selected':''}>${safe(x)}</option>`).join(''); }
function getComponentOptions(selected=''){ return `<option value="">Sin componente</option>`+state.components.map(c=>`<option value="${Number(c.id)}" ${c.id===selected?'selected':''}>${safe(c.name)} · ${safe(c.methodology)}</option>`).join(''); }

function getCurrencyOptions(selected='COP'){
  const currencies = state.defaults?.currencies || ['COP','USD','EUR','MXN','PEN','CLP','BRL'];
  return currencies.map(c=>`<option value="${safe(c)}" ${String(c)===String(selected).toUpperCase()?'selected':''}>${safe(c)}</option>`).join('');
}
function getDependencyTypeOptions(selected='FS'){
  const labels = {FS:'Fin a inicio (FS)', SS:'Inicio a inicio (SS)', FF:'Fin a fin (FF)', SF:'Inicio a fin (SF)'};
  const values = state.defaults?.dependency_types || ['FF','FS','SF','SS'];
  return values.map(v=>`<option value="${safe(v)}" ${v===selected?'selected':''}>${safe(labels[v] || v)}</option>`).join('');
}
function hasChildren(taskId){ return state.tasks.some(t=>Number(t.parent_id)===Number(taskId)); }
function isHiddenByCollapsedAncestor(task, taskMap){
  let parentId = task.parent_id;
  const seen = new Set();
  while(parentId && !seen.has(parentId)){
    seen.add(parentId);
    const parent = taskMap[parentId];
    if(!parent) break;
    if(Number(parent.is_expanded) === 0) return true;
    parentId = parent.parent_id;
  }
  return false;
}
function visibleTasks(){
  const ordered = [...state.tasks].sort((a,b)=>(a.order_index||0)-(b.order_index||0)||a.id-b.id);
  const taskMap = Object.fromEntries(ordered.map(t=>[t.id,t]));
  return ordered.filter(t=>!isHiddenByCollapsedAncestor(t, taskMap));
}
function dependencyTextForTask(taskId){
  return state.dependencies.filter(d=>Number(d.successor_id)===Number(taskId)).map(d=>{
    const pred=state.tasks.find(t=>Number(t.id)===Number(d.predecessor_id));
    return `${pred ? pred.order_index || pred.id : d.predecessor_id}${d.dependency_type || 'FS'}${Number(d.lag_days||0) ? '+'+Number(d.lag_days||0)+'d' : ''}`;
  }).join(', ');
}
function openProject(projectId){ load(Number(projectId)).then(()=>renderView('gantt')); }
function getContextOptions(){
  const options = [`<option value="Proyecto:">Proyecto general</option>`];
  state.components.forEach(c=>options.push(`<option value="Componente:${Number(c.id)}">Componente · ${safe(c.name)}</option>`));
  state.tasks.forEach(t=>options.push(`<option value="Actividad:${Number(t.id)}">Actividad · ${safe(t.title)}</option>`));
  state.risks.forEach(r=>options.push(`<option value="Riesgo:${Number(r.id)}">Riesgo · ${safe(r.title)}</option>`));
  state.deliverables.forEach(d=>options.push(`<option value="Entregable:${Number(d.id)}">Entregable · ${safe(d.name)}</option>`));
  return options.join('');
}
function openTaskModal(id=null, defaultType='task'){
  const p = state.current_project;
  const t = id ? state.tasks.find(x=>x.id===id) : {project_id:p.id,title:'',task_type:defaultType,parent_id:null,start_date:p.start_date,duration_days:defaultType==='milestone'?0:1,progress:0,owner:'',status:'Pendiente',story_points:0,budget:0,description:'',order_index:0,predecessor_id:null,dependency_type:'FS',lag_days:0};
  const existingPred = id ? state.dependencies.find(d=>Number(d.successor_id)===Number(id)) : null;
  openModal(id?'Editar tarea':'Nueva tarea', `<form id="taskForm"><div class="ms-project-note">Crea tareas por duración y predecesoras. La fecha fin se calcula automáticamente; las tareas resumen calculan fechas y avance desde sus hijas.</div><div class="form-grid two">
    <label>Nombre de tarea<input name="title" value="${escapeHtml(t.title)}" required></label>
    <label>Tipo<select name="task_type"><option value="task" ${t.task_type==='task'?'selected':''}>Tarea</option><option value="milestone" ${t.task_type==='milestone'?'selected':''}>Hito</option><option value="summary" ${t.task_type==='summary'?'selected':''}>Tarea resumen</option></select></label>
    <label>Tarea superior<select name="parent_id"><option value="">Nivel principal</option>${state.tasks.filter(x=>!id || x.id!==id).map(x=>`<option value="${Number(x.id)}" ${Number(t.parent_id)===Number(x.id)?'selected':''}>${'— '.repeat(Number(x.outline_level||0))}${safe(x.title)}</option>`).join('')}</select></label>
    <label>Componente<select name="component_id">${getComponentOptions(t.component_id)}</select></label>
    <label>Duración<input name="duration_days" type="number" min="0" value="${t.duration_days ?? (t.task_type==='milestone'?0:1)}"></label>
    <label>Fecha inicio<input name="start_date" type="date" value="${t.start_date || p.start_date}" required></label>
    ${id?`<label>Fecha fin calculada<input value="${safe(t.end_date||'')}" disabled></label>`:''}
    <label>Responsable<select name="owner">${getResourceNamesOptions(t.owner)}</select></label>
    <label>Avance %<input name="progress" type="number" min="0" max="100" value="${t.progress||0}"></label>
    <label>Estado<input name="status" value="${escapeHtml(t.status||'Pendiente')}"></label>
    <label>Story points<input name="story_points" type="number" min="0" value="${t.story_points||0}"></label>
    <label>Presupuesto<input name="budget" type="number" min="0" value="${t.budget||0}"></label>
    <label>Predecesora<select name="predecessor_id">${getTaskOptions(existingPred?.predecessor_id || '', id)}</select></label>
    <label>Tipo dependencia<select name="dependency_type">${getDependencyTypeOptions(existingPred?.dependency_type || 'FS')}</select></label>
    <label>Desfase / lag días<input name="lag_days" type="number" value="${Number(existingPred?.lag_days || 0)}"></label>
  </div><label>Descripción<textarea name="description" rows="3">${escapeHtml(t.description||'')}</textarea></label>${modalActions(id?'Actualizar tarea':'Crear tarea')}</form>`);
  const typeField = $('#taskForm [name="task_type"]');
  const durField = $('#taskForm [name="duration_days"]');
  typeField?.addEventListener('change',()=>{ if(typeField.value==='milestone') durField.value=0; if(typeField.value==='summary' && Number(durField.value||0)<1) durField.value=1; });
  $('#taskForm').addEventListener('submit', async e=>{
    e.preventDefault();
    const fd=new FormData(e.target); const body=Object.fromEntries(fd.entries());
    const predecessorId = body.predecessor_id ? Number(body.predecessor_id) : null;
    const dependencyType = body.dependency_type || 'FS';
    const lagDays = Number(body.lag_days || 0);
    body.project_id=state.current_project.id;
    body.progress=Number(body.progress||0); body.story_points=Number(body.story_points||0); body.budget=Number(body.budget||0); body.duration_days=Number(body.duration_days||0);
    if(!body.component_id) delete body.component_id; else body.component_id=Number(body.component_id);
    if(!body.parent_id) delete body.parent_id; else body.parent_id=Number(body.parent_id);
    if(!predecessorId) delete body.predecessor_id; else body.predecessor_id=predecessorId;
    body.dependency_type=dependencyType;
    body.lag_days=lagDays;
    delete body.order_index; delete body.phase; delete body.end_date;
    if(id){
      delete body.predecessor_id;
      delete body.dependency_type;
      delete body.lag_days;
      await request(`/api/tasks/${id}`, {method:'PUT', body:JSON.stringify(body)});
      if(existingPred && (!predecessorId || Number(existingPred.predecessor_id)!==Number(predecessorId))){
        await request(`/api/dependencies/${Number(existingPred.id)}`, {method:'DELETE'});
      }
      if(predecessorId){
        await request('/api/dependencies', {method:'POST', body:JSON.stringify({project_id:state.current_project.id, predecessor_id:predecessorId, successor_id:id, dependency_type:dependencyType, lag_days:lagDays})});
      }
    }else{
      await request('/api/tasks', {method:'POST', body:JSON.stringify(body)});
    }
    closeModal(); toast(id?'Tarea actualizada y cronograma recalculado':'Tarea creada y cronograma recalculado'); await load(state.current_project.id);
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
    <label>Estrategia<select name="response"><option>Mitigar</option><option>Evitar</option><option>Transferir</option><option>Aceptar</option></select></label>
    <label>Estado<select name="status"><option>Abierto</option><option>En tratamiento</option><option>Materializado</option><option>Cerrado</option></select></label>
  </div><label>Plan de mitigación<textarea name="mitigation_plan" rows="3" placeholder="Acciones para reducir probabilidad o impacto"></textarea></label><label>Plan de contingencia<textarea name="contingency_plan" rows="3" placeholder="Acciones si el riesgo se materializa"></textarea></label>${modalActions('Crear')}</form>`);
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
function openConversationModal(){
  openModal('Nuevo hilo de conversacion', `<form id="conversationForm"><div class="form-grid two">
    <label>Titulo<input name="title" required placeholder="Acuerdo sobre hito comprometido"></label>
    <label>Contexto<select name="context">${getContextOptions()}</select></label>
    <label>Categoria<select name="category"><option>Seguimiento</option><option>Decision</option><option>Bloqueo</option><option>Acuerdo</option></select></label>
    <label>Creado por<select name="created_by">${getResourceNamesOptions()}</select></label>
  </div>${modalActions('Crear hilo')}</form>`);
  $('#conversationForm').addEventListener('submit', async e=>{
    e.preventDefault();
    const body=Object.fromEntries(new FormData(e.target).entries());
    const [context_type, rawId] = body.context.split(':');
    body.project_id=state.current_project.id;
    body.context_type=context_type;
    body.context_id=rawId?Number(rawId):null;
    delete body.context;
    const created = await request('/api/conversations',{method:'POST',body:JSON.stringify(body)});
    state.active_thread_id = created.id;
    closeModal(); toast('Hilo creado'); await load(state.current_project.id); renderView('conversations');
  });
}
async function sendMessage(e){
  e.preventDefault();
  const thread = activeThread();
  if(!thread){ toast('Crea o selecciona una conversacion'); return; }
  const text = $('#messageText').value.trim();
  if(!text){ toast('Escribe un mensaje'); return; }
  const body = {
    thread_id: thread.id,
    project_id: state.current_project.id,
    author: $('#messageAuthor').value,
    message: text,
    mentions: $('#messageMentions').value,
    evidence_url: $('#messageEvidence').value,
    message_type: $('#messageType').value
  };
  await request(`/api/conversations/${thread.id}/messages`,{method:'POST',body:JSON.stringify(body)});
  $('#messageText').value=''; $('#messageMentions').value=''; $('#messageEvidence').value='';
  toast('Mensaje registrado'); await load(state.current_project.id); renderView('conversations');
}
function openComponentModal(){
  openModal('Nuevo componente', `<form id="componentForm"><div class="form-grid two">
    <label>Nombre<input name="name" required placeholder="Componente cientifico"></label>
    <label>Metodologia<select name="methodology"><option>Tradicional</option><option>Scrum</option><option>Kanban</option><option>Hibrida</option></select></label>
    <label>Responsable<select name="owner">${getResourceNamesOptions()}</select></label>
    <label>Avance %<input name="progress" type="number" min="0" max="100" value="0"></label>
  </div><label>Objetivo<textarea name="objective" rows="3"></textarea></label>${modalActions('Crear')}</form>`);
  $('#componentForm').addEventListener('submit', async e=>{ e.preventDefault(); const body=Object.fromEntries(new FormData(e.target).entries()); body.project_id=state.current_project.id; body.progress=Number(body.progress||0); await request('/api/components',{method:'POST',body:JSON.stringify(body)}); closeModal(); toast('Componente creado'); await load(state.current_project.id); });
}
function openDeliverableModal(){
  openModal('Nuevo producto o evidencia', `<form id="deliverableForm"><div class="form-grid two">
    <label>Nombre<input name="name" required></label>
    <label>Tipo<select name="deliverable_type"><option>Entregable</option><option>Producto de conocimiento</option><option>Evidencia</option><option>Informe</option></select></label>
    <label>Componente<select name="component_id">${getComponentOptions()}</select></label>
    <label>Estado<select name="status"><option>Planeado</option><option>En progreso</option><option>En revision</option><option>Aprobado</option><option>Cerrado</option></select></label>
    <label>Responsable<select name="owner">${getResourceNamesOptions()}</select></label>
    <label>Fecha compromiso<input name="due_date" type="date"></label>
  </div><label>URL evidencia<input name="evidence_url" placeholder="https://..."></label><label>Descripcion<textarea name="description" rows="3"></textarea></label>${modalActions('Crear')}</form>`);
  $('#deliverableForm').addEventListener('submit', async e=>{ e.preventDefault(); const body=Object.fromEntries(new FormData(e.target).entries()); body.project_id=state.current_project.id; body.component_id=body.component_id?Number(body.component_id):null; if(!body.due_date) delete body.due_date; await request('/api/deliverables',{method:'POST',body:JSON.stringify(body)}); closeModal(); toast('Producto registrado'); await load(state.current_project.id); });
}
function openNewProjectModal(){
  const today = iso(new Date());
  openModal('Nuevo proyecto', `<form id="projectForm"><div class="form-grid two">
    <label>Nombre<input name="name" required value="Nuevo proyecto"></label>
    <label>Project Manager<input name="project_manager" value=""></label>
    <label>Sponsor<input name="sponsor" value=""></label>
    <label>Fecha inicio<input name="start_date" type="date" value="${today}"></label>
    <label>Fecha compromiso / contractual<input name="contractual_end_date" type="date"></label>
    <label>Presupuesto<input name="budget" type="number" value="0"></label>
    <label>Moneda<select name="currency">${getCurrencyOptions('COP')}</select></label>
    <label>Metodología<select name="methodology"><option>Híbrida PMP + Scrum</option><option>Tradicional PMP</option><option>Ágil Scrum</option><option>Kanban</option><option>Híbrida personalizada</option></select></label>
  </div><p class="field-help">La fecha fin del proyecto no se digita manualmente: se calcula con duración, predecesoras y cronograma.</p><label>Descripción<textarea name="description" rows="3">Proyecto creado desde Proyecta360.</textarea></label>${modalActions('Crear proyecto')}</form>`);
  $('#projectForm').addEventListener('submit', async e=>{ e.preventDefault(); const body=Object.fromEntries(new FormData(e.target).entries()); body.budget=Number(body.budget||0); body.status='Planeado'; if(!body.contractual_end_date) delete body.contractual_end_date; body.parameters=state.defaults; const created=await request('/api/projects',{method:'POST', body:JSON.stringify(body)}); closeModal(); toast('Proyecto creado con fecha fin calculada'); await load(created.id); renderView('parameters'); });
}
function openLoginModal(){
  openModal('Ingreso', `<form id="loginForm"><div class="form-grid two">
    <label>Correo<input name="email" type="email" autocomplete="username" required></label>
    <label>Contrase?a<input name="password" type="password" autocomplete="current-password" required></label>
  </div><p class="auth-demo">Ingresa con una cuenta autorizada.</p>${modalActions('Ingresar')}</form>`);
}
async function submitLogin(e){
  e.preventDefault();
  const form = e.target.closest?.('form') || e.target;
  const body = Object.fromEntries(new FormData(form).entries());
  const res = await request('/api/auth/login',{method:'POST', body:JSON.stringify(body)});
  localStorage.setItem(AUTH_TOKEN_KEY, res.token);
  state.current_user = res.user;
  closeModal();
  toast(`Sesi?n iniciada: ${res.user.name}`);
  await load(state.current_project?.id);
}
function submitAuthGateLogin(e){
  e?.preventDefault?.();
  const form = $('#authGateForm');
  if(!form?.reportValidity()) return;
  submitLogin({preventDefault(){}, target: form}).catch(err=>{
    console.error(err);
    toast(err.message);
  });
}
async function logout(){
  await request('/api/auth/logout',{method:'POST', body:JSON.stringify({})}).catch(()=>null);
  localStorage.removeItem(AUTH_TOKEN_KEY);
  state.current_user = null;
  showAuthGate();
  toast('Sesi?n cerrada');
}
function downloadUrl(url){
  const a=document.createElement('a'); a.href=url; a.target='_blank'; document.body.appendChild(a); a.click(); a.remove();
}
async function exportJson(){ downloadUrl(`/api/projects/${state.current_project.id}/export/json`); setTimeout(()=>load(state.current_project.id),800); }
async function exportHtml(){ downloadUrl(`/api/projects/${state.current_project.id}/export/html`); setTimeout(()=>load(state.current_project.id),800); }
function renderAiProviderFields(settings={}){
  const form = $('#aiSettingsForm');
  const select = $('#aiProviderSelect');
  const fieldsBox = $('#aiProviderFields');
  if(!form || !select || !fieldsBox) return;
  const providers = settings.providers || state.ai_providers || {};
  state.ai_providers = providers;
  const provider = settings.provider || select.value || 'openai';
  select.innerHTML = Object.entries(providers).map(([key, item])=>`<option value="${safe(key)}" ${key===provider?'selected':''}>${safe(item.name)}</option>`).join('');
  const definition = providers[provider] || providers.openai || {fields:[]};
  const config = settings.config || {};
  const useProviderDefault = Boolean(settings.useProviderDefault);
  const providerDefaults = Object.entries(providers)
    .filter(([key, item])=>key !== provider && item.default_model)
    .flatMap(([, item])=>[item.default_model].concat((item.model_options || []).map(option=>option.value)));
  const inheritedModel = settings.model && providerDefaults.includes(settings.model);
  fieldsBox.innerHTML = (definition.fields || []).filter(field=>field.required).map(field=>{
    const required = field.required ? 'required' : '';
    const placeholder = field.name === 'api_key'
      ? (settings.api_key_masked || field.placeholder || 'No configurada')
      : (field.placeholder || '');
    const value = field.name === 'model'
      ? ((useProviderDefault || inheritedModel) ? (definition.default_model || '') : (settings.model || definition.default_model || ''))
      : (field.name === 'api_key' ? '' : (config[field.name] || ''));
    if(field.name === 'model' && (definition.model_options || []).length){
      const hasValue = (definition.model_options || []).some(option=>option.value === value);
      const options = (definition.model_options || []).map(option=>`<option value="${safe(option.value)}" ${option.value===value?'selected':''}>${safe(option.label || option.value)}</option>`).join('');
      const customOption = hasValue || !value ? '' : `<option value="${safe(value)}" selected>${safe(value)} (actual)</option>`;
      return `<label>${safe(field.label)}<select name="model" ${required}>${customOption}${options}</select></label>`;
    }
    return `<label>${safe(field.label)}<input name="${safe(field.name)}" type="${safe(field.type || 'text')}" ${required} placeholder="${safe(placeholder)}" value="${safe(value)}"></label>`;
  }).join('');
}
function setAiTab(tab){
  $$('.ai-tabs [data-ai-tab]').forEach(btn=>btn.classList.toggle('active', btn.dataset.aiTab === tab));
  $$('.ai-tab-panel').forEach(panel=>panel.classList.add('hidden'));
  $(`#aiTab-${tab}`)?.classList.remove('hidden');
  if(tab === 'settings') loadAiSettings();
  if(tab === 'recommendations') refreshAiRecommendations();
  if(tab === 'history') refreshAiHistory();
}
async function loadAiSettings(){
  const form = $('#aiSettingsForm');
  const res = await request('/api/ai/settings');
  const connected = res.status === 'Conectado';
  if(form){
    renderAiProviderFields(res);
    $('#aiSettingsStatus').textContent = `Estado: ${res.status || 'No configurado'}${res.last_error ? ' | '+res.last_error : ''}`;
  }
  const notice = $('#aiModeNotice');
  if(notice) notice.textContent = connected ? `${res.provider_name || 'IA real'} configurada` : 'Motor interno activo';
  const runBtn = $('#btnRunAiAnalysis');
  if(runBtn) runBtn.textContent = connected ? 'Analizar proyecto con IA real' : 'Analizar proyecto con motor interno';
}
async function saveAiSettings(e, options={}){
  e?.preventDefault?.();
  const form = $('#aiSettingsForm');
  if(!form?.reportValidity()) return;
  const btn = $('#btnSaveAiSettings');
  btn && (btn.disabled = true);
  const silent = Boolean(options.silent);
  $('#aiSettingsStatus').textContent = silent ? 'Estado: Preparando prueba...' : 'Estado: Guardando configuracion...';
  try{
    const raw = Object.fromEntries(new FormData(form).entries());
    const body = {provider: raw.provider || 'openai', model: raw.model || '', api_key: raw.api_key || '', config: {}};
    Object.entries(raw).forEach(([key, value])=>{
      if(!['provider','model','api_key'].includes(key)) body.config[key] = value;
    });
    const res = await request('/api/ai/settings',{method:'POST', body:JSON.stringify(body)});
    $('#aiSettingsStatus').textContent = `Estado: ${res.status}`;
    if(!silent) toast('Configuracion IA guardada');
    if(!silent) await loadAiSettings();
    return res;
  }catch(err){
    console.error(err);
    $('#aiSettingsStatus').textContent = `Estado: Error | ${err.message}`;
    if(!silent) toast(err.message);
    if(silent) throw err;
    return null;
  }finally{
    btn && (btn.disabled = false);
  }
}
async function testAiConnection(){
  const btn = $('#btnTestAiConnection');
  btn && (btn.disabled = true);
  $('#aiSettingsStatus').textContent = 'Estado: Probando conexion...';
  try{
    await saveAiSettings(null, {silent: true});
    $('#aiSettingsStatus').textContent = 'Estado: Probando conexion...';
    const res = await request('/api/ai/test-connection',{method:'POST', body:JSON.stringify({})});
    $('#aiSettingsStatus').textContent = `Estado: ${res.status} | ${res.message}`;
    toast(res.message);
    await loadAiSettings();
  }catch(err){
    console.error(err);
    $('#aiSettingsStatus').textContent = `Estado: Error | ${err.message}`;
    toast(err.message);
  }finally{
    btn && (btn.disabled = false);
  }
}
async function clearAiSettings(){
  await request('/api/ai/settings',{method:'DELETE'});
  toast('Configuracion IA eliminada');
  await loadAiSettings();
}
function aiAnalysisIncludes(){
  return Object.fromEntries($$('[data-ai-include]').map(input=>[input.dataset.aiInclude, input.checked]));
}
async function runAiAnalysis(){
  if(!state.current_project?.id){ toast('Selecciona un proyecto primero'); return; }
  const btn = $('#btnRunAiAnalysis');
  const output = $('#aiOutput');
  const previous = btn?.textContent || '';
  if(btn){ btn.disabled = true; btn.textContent = 'Analizando...'; }
  if(output) output.textContent = 'Analizando el proyecto con el motor disponible...';
  try{
    const res = await request(`/api/projects/${state.current_project.id}/ai/analyze`,{method:'POST', body:JSON.stringify(aiAnalysisIncludes())});
    const engine = res.engine_label || (res.mode === 'configured' ? 'IA real' : 'Motor interno');
    const issues = (res.detected_issues || []).map(item=>`- [${item.severity || 'info'}] ${item.description}`).join('\n');
    const recs = (res.recommended_actions || []).map(item=>`- [${item.priority || 'medium'}] ${item.title}: ${item.description}`).join('\n');
    output.textContent = `${res.analysis_notice || res.demo_notice || ''}\n\nMotor: ${engine}\nSalud: ${res.project_health}\n\n${res.summary}\n\nHallazgos:\n${issues || '- Sin hallazgos relevantes'}\n\nRecomendaciones pendientes:\n${recs || '- Sin recomendaciones'}`;
    toast('Analisis IA generado');
    await refreshAiRecommendations();
    await refreshAiHistory();
    await loadAiSettings();
  }catch(err){
    console.error(err);
    if(output) output.textContent = `No fue posible generar el analisis.\n\nDetalle: ${err.message}`;
    toast(err.message);
  }finally{
    if(btn){ btn.disabled = false; btn.textContent = previous || 'Analizar proyecto completo'; }
    await loadAiSettings().catch(()=>null);
  }
}
async function aiProjectAsk(){
  const q = $('#aiQuestion')?.value.trim();
  if(!q){ toast('Escribe una pregunta para el proyecto'); return; }
  const mode = $('#aiChatMode')?.value || 'consulta';
  const res = await request(`/api/projects/${state.current_project.id}/ai/chat`,{method:'POST', body:JSON.stringify({message:q, mode})});
  $('#aiOutput').textContent = mode === 'accion'
    ? `Modo accion:\n${res.answer}\n\nRecomendaciones pendientes generadas: ${(res.recommendation_ids||[]).length}`
    : `Pregunta:\n${q}\n\nRespuesta conectada al proyecto:\n${res.answer}`;
  toast(mode === 'accion' ? 'Recomendaciones pendientes creadas' : 'Respuesta IA generada');
  if(mode === 'accion') await refreshAiRecommendations();
}
async function refreshAiRecommendations(){
  if(!state.current_project) return;
  const box = $('#aiRecommendationsTable');
  if(!box) return;
  const res = await request(`/api/projects/${state.current_project.id}/ai/recommendations`);
  const rows = res.recommendations || [];
  box.innerHTML = rows.length ? `<div class="ai-rec-row ai-rec-head"><span>Prioridad</span><span>Accion</span><span>Modulo</span><span>Estado</span><span>Impacto</span><span>Acciones</span></div>${rows.map(r=>`<div class="ai-rec-row"><span class="pill ${r.priority==='high'?'pill-red':r.priority==='low'?'pill-green':'pill-amber'}">${safe(r.priority)}</span><b>${safe(r.title)}</b><span>${safe(r.target_module||'-')}</span><span>${safe(r.status)}</span><span>${safe(r.expected_impact||'-')}</span><span class="ai-row-actions"><button class="btn tiny" data-ai-rec="detail" data-id="${Number(r.id)}">Ver</button><button class="btn tiny" data-ai-rec="edit" data-id="${Number(r.id)}">Editar</button><button class="btn tiny" data-ai-rec="approve" data-id="${Number(r.id)}">Aprobar</button><button class="btn tiny" data-ai-rec="reject" data-id="${Number(r.id)}">Rechazar</button><button class="btn tiny" data-ai-rec="apply" data-id="${Number(r.id)}">Aplicar</button></span></div>`).join('')}` : '<p>No hay recomendaciones IA para este proyecto.</p>';
}
async function refreshAiHistory(){
  if(!state.current_project) return;
  const list = $('#aiHistoryList');
  if(!list) return;
  const res = await request(`/api/projects/${state.current_project.id}/ai/history`);
  list.innerHTML = (res.history||[]).map(r=>`<div class="history-item"><b>${safe(r.project_health||'Analisis IA')}</b><span>${safe(r.summary||'')}</span><small>${safe(r.started_at||'')} | Issues: ${Number(r.issues_count||0)} | Recs: ${Number(r.recommendations_count||0)} | Aprobadas: ${Number(r.approved_count||0)} | Rechazadas: ${Number(r.rejected_count||0)} | Aplicadas: ${Number(r.applied_count||0)}</small></div>`).join('') || '<p>No hay historial IA.</p>';
}
async function handleAiRecommendation(action, id){
  if(action === 'detail'){
    const r = await request(`/api/ai/recommendations/${id}`);
    openModal('Detalle recomendacion IA', `<pre>${safe(JSON.stringify(r, null, 2))}</pre>`);
    return;
  }
  if(action === 'edit'){
    const r = await request(`/api/ai/recommendations/${id}`);
    openModal('Editar recomendacion IA', `<form id="aiRecEditForm"><label>Titulo<input name="title" value="${escapeHtml(r.title)}"></label><label>Descripcion<textarea name="description" rows="3">${escapeHtml(r.description||'')}</textarea></label><label>Payload aprobado<textarea name="edited_payload" rows="8">${escapeHtml(JSON.stringify(r.edited_payload || r.proposed_payload || {}, null, 2))}</textarea></label>${modalActions('Guardar cambios')}</form>`);
    $('#aiRecEditForm').addEventListener('submit', async e=>{
      e.preventDefault();
      let edited;
      try{ edited = JSON.parse(e.target.edited_payload.value || '{}'); }catch(err){ toast('Payload JSON invalido'); return; }
      await request(`/api/ai/recommendations/${id}`,{method:'PATCH', body:JSON.stringify({title:e.target.title.value, description:e.target.description.value, edited_payload:edited})});
      closeModal(); toast('Recomendacion editada'); await refreshAiRecommendations();
    });
    return;
  }
  const verb = {approve:'approve', reject:'reject', apply:'apply'}[action];
  if(!verb) return;
  await request(`/api/ai/recommendations/${id}/${verb}`,{method:'POST', body:JSON.stringify({})});
  toast(action === 'approve' ? 'Recomendacion aprobada' : action === 'reject' ? 'Recomendacion rechazada' : 'Recomendacion aplicada');
  await load(state.current_project.id);
  renderView('ai');
  setAiTab('recommendations');
}

function bindEvents(){
  on('#authGateSubmit','click',submitAuthGateLogin);
  document.addEventListener('submit', e=>{
    if(e.target?.id === 'authGateForm' || e.target?.id === 'loginForm'){
      submitLogin(e).catch(err=>{
        console.error(err);
        toast(err.message);
      });
    }
  });
  document.addEventListener('click', e=>{
    const aiRec = e.target.closest?.('[data-ai-rec]');
    if(aiRec){
      e.preventDefault();
      e.stopPropagation();
      return handleAiRecommendation(aiRec.dataset.aiRec, Number(aiRec.dataset.id || 0));
    }
    const actionEl = e.target.closest?.('[data-action]');
    if(!actionEl) return;
    e.preventDefault();
    e.stopPropagation();
    const id = Number(actionEl.dataset.id || 0);
    const action = actionEl.dataset.action;
    if(action === 'save-ai-settings') return saveAiSettings(e);
    if(action === 'test-ai-connection') return testAiConnection(e);
    if(action === 'clear-ai-settings') return clearAiSettings();
    if(action === 'open-project') return openProject(id);
    if(action === 'toggle-task') return toggleTask(id);
    if(action === 'indent-task') return indentTask(id);
    if(action === 'outdent-task') return outdentTask(id);
    if(action === 'edit-task') return openTaskModal(id);
    if(action === 'remove-task') return removeTask(id);
    if(action === 'move-story') return moveStory(id, actionEl.dataset.status || '');
    if(action === 'select-thread') return selectThread(id);
    if(action === 'select-task'){ state.selected_task_id = id; renderGantt(); return; }
    if(action === 'gantt-scale'){
      state.gantt_scale = actionEl.dataset.scale || 'days';
      state.gantt_fit_px = null;
      state.gantt_manual_zoom = false;
      renderGantt();
      return;
    }
    if(action === 'zoom-out'){
      state.gantt_fit_px = null;
      state.gantt_manual_zoom = true;
      const idx = zoomLevels.findIndex(level=>level >= state.gantt_zoom);
      state.gantt_zoom = zoomLevels[Math.max(0, (idx < 0 ? zoomLevels.length - 1 : idx) - 1)];
      renderGantt();
      return;
    }
    if(action === 'zoom-in'){
      state.gantt_fit_px = null;
      state.gantt_manual_zoom = true;
      const idx = zoomLevels.findIndex(level=>level > state.gantt_zoom);
      state.gantt_zoom = zoomLevels[Math.min(zoomLevels.length - 1, idx < 0 ? zoomLevels.length - 1 : idx)];
      renderGantt();
      return;
    }
    if(action === 'zoom-fit'){
      state.gantt_manual_zoom = false;
      return fitGanttToViewport();
    }
  });
  document.addEventListener('change', e=>{
    if(e.target?.id === 'aiProviderSelect'){
      renderAiProviderFields({provider: e.target.value, providers: state.ai_providers || {}, useProviderDefault: true});
    }
  });
  $$('.side-item,.top-tab').forEach(b=>b.addEventListener('click',()=>renderView(b.dataset.view || 'gantt')));
  $$('.ai-tabs [data-ai-tab]').forEach(b=>b.addEventListener('click',()=>setAiTab(b.dataset.aiTab)));
  on('#projectSelector','change', e=>load(Number(e.target.value)));
  on('#btnReload','click',()=>load(state.current_project.id));
  on('#btnAddTask','click',()=>openTaskModal());
  on('#btnGanttAddTask','click',()=>openTaskModal());
  on('#btnGanttAddMilestone','click',()=>openTaskModal(null,'milestone'));
  on('#btnGanttIndent','click',()=> state.selected_task_id ? indentTask(state.selected_task_id) : toast('Selecciona una tarea primero'));
  on('#btnGanttOutdent','click',()=> state.selected_task_id ? outdentTask(state.selected_task_id) : toast('Selecciona una tarea primero'));
  on('#btnAiPlan','click',()=>{ renderView('ai'); setAiTab('analysis'); $('#view-ai')?.scrollIntoView({behavior:'smooth', block:'start'}); });
  on('#ganttZoomRange','input',e=>{
    state.gantt_fit_px = null;
    state.gantt_manual_zoom = true;
    state.gantt_zoom = Number(e.target.value || 1);
    renderGantt();
  });
  on('#btnOpenParameters','click',()=>renderView('parameters'));
  on('#btnSaveParametersInline','click',saveParameters);
  on('#btnNewProject','click',openNewProjectModal);
  on('#btnAddStory','click',openStoryModal);
  on('#btnAddRisk','click',openRiskModal);
  on('#btnAddResource','click',openResourceModal);
  on('#btnAddConversation','click',openConversationModal);
  on('#btnAddComponent','click',openComponentModal);
  on('#btnAddDeliverable','click',openDeliverableModal);
  on('#btnUploadEvidence','click',openEvidenceModal);
  on('#btnUploadEvidenceSecondary','click',openEvidenceModal);
  on('#aiSettingsForm','submit',saveAiSettings);
  on('#btnRunAiAnalysis','click',runAiAnalysis);
  on('#btnRefreshAiRecommendations','click',refreshAiRecommendations);
  on('#btnRefreshAiHistory','click',refreshAiHistory);
  on('#btnExportJson','click',exportJson);
  on('#btnExportHtml','click',exportHtml);
  on('#btnAskAi','click',aiProjectAsk);
  on('#btnLogin','click',openLoginModal);
  on('#btnLogout','click',logout);
  on('#messageForm','submit',sendMessage);
  window.addEventListener('resize',()=>{
    if(state.view !== 'gantt') return;
    if(!state.gantt_manual_zoom){
      state.gantt_fit_px = null;
      renderGantt();
      return;
    }
    drawDependencies();
  });
}

window.openTaskModal = openTaskModal;
window.indentTask = indentTask;
window.outdentTask = outdentTask;
window.toggleTask = toggleTask;
window.openProject = openProject;
window.removeTask = removeTask;
window.moveStory = moveStory;
window.selectThread = selectThread;
window.load = load;
window.exportJson = exportJson;
window.exportHtml = exportHtml;
window.submitAuthGateLogin = submitAuthGateLogin;

bindEvents();
scrubCredentialQuery();
if(localStorage.getItem(AUTH_TOKEN_KEY)){
  load().catch(err=>{ console.error(err); toast(err.message); });
}else{
  showAuthGate();
}

