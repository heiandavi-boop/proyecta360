// Global application state shared across all views.
export const state = {
  projects: [],
  current_project: null,
  tasks: [],
  dependencies: [],
  sprints: [],
  stories: [],
  risks: [],
  resources: [],
  metrics: {},
  defaults: {},
  view: 'gantt',
};

// Merge a bootstrap payload (or any partial) into the shared state object.
export function setState(patch) {
  Object.assign(state, patch);
}
