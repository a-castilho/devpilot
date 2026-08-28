(() => {
  'use strict';

  const GAME_TASK_LIMIT = 24;
  const GAME_PROJECT_LIMIT = 50;
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const originalApi = window.api;

  const now = () => typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? Math.round(performance.now())
    : Date.now();

  const trace = (stage, detail = {}) => {
    const entry = {stage, at: now(), ...detail};
    if (!Array.isArray(window.__devpilotGameBootTrace)) window.__devpilotGameBootTrace = [];
    window.__devpilotGameBootTrace.push(entry);
    console.debug('[DevPilot Game Trace]', entry);
    return entry;
  };

  window.__devpilotGameTrace = trace;
  trace('guard:ready');

  if (typeof originalApi !== 'function') {
    trace('guard:error', {message: 'api indisponível'});
    return;
  }

  window.api = async (path, options = {}) => {
    const requestPath = String(path || '');
    let routedPath = path;
    let stage = 'api';

    if (requestPath === '/projects' || requestPath.startsWith('/projects?')) {
      const savedProjectId = String(localStorage.getItem(GAME_PROJECT_KEY) || '').trim();
      const includeProject = savedProjectId
        ? `&include_project_id=${encodeURIComponent(savedProjectId)}`
        : '';
      routedPath = `/ui/projects?limit=${GAME_PROJECT_LIMIT}${includeProject}`;
      stage = 'projects';
    } else {
      const isGameTaskList = requestPath.startsWith('/tasks?') && requestPath.includes('project_id=');
      if (isGameTaskList) {
        const params = new URLSearchParams(requestPath.split('?')[1] || '');
        const projectId = params.get('project_id');
        if (projectId) {
          routedPath = `/ui/game-tasks?project_id=${encodeURIComponent(projectId)}&limit=${GAME_TASK_LIMIT}`;
          stage = 'game-tasks';
        }
      }
    }

    trace(`${stage}:start`, {path: String(routedPath || '')});
    try {
      const result = await originalApi(routedPath, options);
      trace(`${stage}:end`, {count: Array.isArray(result) ? result.length : undefined});
      return result;
    } catch (error) {
      if (stage === 'projects' || stage === 'game-tasks') {
        window.__devpilotGameLoadError = error instanceof Error
          ? error
          : new Error(String(error || 'Falha ao carregar o Modo Jogo'));
      }
      trace(`${stage}:error`, {message: String(error?.message || error || 'erro')});
      throw error;
    }
  };

  window.__devpilotGameTaskLimit = GAME_TASK_LIMIT;
  window.__devpilotGameProjectLimit = GAME_PROJECT_LIMIT;
  window.__devpilotGameUsesLightweightHistory = true;
  window.__devpilotGameUsesLightweightProjects = true;
})();
