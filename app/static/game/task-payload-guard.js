(() => {
  'use strict';

  const GAME_TASK_LIMIT = 24;
  const originalApi = window.api;

  if (typeof originalApi !== 'function') return;

  window.api = (path, options = {}) => {
    const requestPath = String(path || '');
    const isGameTaskList = requestPath.startsWith('/tasks?') && requestPath.includes('project_id=');

    if (!isGameTaskList) return originalApi(path, options);

    const params = new URLSearchParams(requestPath.split('?')[1] || '');
    const projectId = params.get('project_id');
    if (!projectId) return originalApi(path, options);

    const lightweightPath = `/ui/game-tasks?project_id=${encodeURIComponent(projectId)}&limit=${GAME_TASK_LIMIT}`;
    return originalApi(lightweightPath, options);
  };

  window.__devpilotGameTaskLimit = GAME_TASK_LIMIT;
  window.__devpilotGameUsesLightweightHistory = true;
})();
