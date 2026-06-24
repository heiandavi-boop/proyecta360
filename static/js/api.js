// API layer: the fetch wrapper plus one function per backend endpoint.
// No DOM access and no rendering happens here.

const API = '';

export async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!res.ok) {
    let detail = 'Error en la operación';
    try {
      detail = (await res.json()).detail || detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

export function bootstrap(projectId) {
  const query = projectId ? `?project_id=${projectId}` : '';
  return request(`/api/bootstrap${query}`);
}

// Projects
export function createProject(body) {
  return request('/api/projects', { method: 'POST', body: JSON.stringify(body) });
}
export function updateProject(id, body) {
  return request(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify(body) });
}

// Tasks
export function createTask(body) {
  return request('/api/tasks', { method: 'POST', body: JSON.stringify(body) });
}
export function updateTask(id, body) {
  return request(`/api/tasks/${id}`, { method: 'PUT', body: JSON.stringify(body) });
}
export function deleteTask(id) {
  return request(`/api/tasks/${id}`, { method: 'DELETE' });
}

// Stories
export function createStory(body) {
  return request('/api/stories', { method: 'POST', body: JSON.stringify(body) });
}
export function updateStory(id, body) {
  return request(`/api/stories/${id}`, { method: 'PUT', body: JSON.stringify(body) });
}

// Risks
export function createRisk(body) {
  return request('/api/risks', { method: 'POST', body: JSON.stringify(body) });
}

// Resources
export function createResource(body) {
  return request('/api/resources', { method: 'POST', body: JSON.stringify(body) });
}

// AI
export function aiGeneratePlan(body) {
  return request('/api/ai/generate-plan', { method: 'POST', body: JSON.stringify(body) });
}
export function aiReport(body) {
  return request('/api/ai/report', { method: 'POST', body: JSON.stringify(body) });
}
