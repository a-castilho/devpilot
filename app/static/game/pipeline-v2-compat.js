(() => {
  'use strict';

  const PIPELINE_MARKER = '[DEVPILOT_BUILD_GAME_PIPELINE_V2]';
  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const originalApi = window.api;

  if (typeof originalApi !== 'function' || window.__devpilotGamePipelineV2Compat) return;
  window.__devpilotGamePipelineV2Compat = true;

  const restoreMarker = task => {
    if (!task || typeof task !== 'object') return task;
    const title = String(task.title || '');
    const prompt = String(task.prompt || '');
    if (!title.startsWith('[Jogo] Etapa ') || !prompt.includes(GAME_MARKER) || prompt.includes(PIPELINE_MARKER)) {
      return task;
    }
    return {...task, prompt: `${prompt}\n${PIPELINE_MARKER}`};
  };

  window.api = async (path, options = {}) => {
    const result = await originalApi(path, options);
    const requestPath = String(path || '');
    if (!requestPath.startsWith('/ui/game-tasks?')) return result;
    return Array.isArray(result) ? result.map(restoreMarker) : result;
  };
})();