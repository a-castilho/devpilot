(() => {
  'use strict';

  const GAME_TASK_LIMIT = 100;
  const originalApi = window.api;

  if (typeof originalApi !== 'function') return;

  window.api = (path, options = {}) => {
    const requestPath = String(path || '');
    const isGameTaskList = requestPath.startsWith('/tasks?') && requestPath.includes('limit=500');
    const boundedPath = isGameTaskList
      ? requestPath.replace(/([?&]limit=)500\b/, `$1${GAME_TASK_LIMIT}`)
      : path;

    return originalApi(boundedPath, options);
  };

  window.__devpilotGameTaskLimit = GAME_TASK_LIMIT;
})();
