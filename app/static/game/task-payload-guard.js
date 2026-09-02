(() => {
  'use strict';

  if (window.__devpilotGameTaskGuardV73) return;
  window.__devpilotGameTaskGuardV73 = true;

  const originalApi = window.api;
  if (typeof originalApi !== 'function') return;

  const locks = new Map();
  const recentCreations = new Map();
  const RECENT_CREATION_TTL_MS = 60000;
  const FAILED = new Set(['failed', 'cancelled', 'canceled', 'archived']);

  const now = () => typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? Math.round(performance.now())
    : Date.now();
  const wallNow = () => Date.now();

  const trace = (stage, detail = {}) => {
    const rows = Array.isArray(window.__devpilotGameBootTrace)
      ? window.__devpilotGameBootTrace
      : (window.__devpilotGameBootTrace = []);
    rows.push({stage, at: now(), ...detail});
    if (rows.length > 48) rows.splice(0, rows.length - 48);
    if (localStorage.getItem('devpilot-game-debug') === '1') console.debug('[DevPilot Game Trace]', rows.at(-1));
  };

  const promptValue = (prompt, label) => {
    const escaped = String(label || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
  };

  const payloadFrom = options => {
    try { return JSON.parse(String(options?.body || '{}')); }
    catch (_) { return {}; }
  };

  const identityFrom = options => {
    const payload = payloadFrom(options);
    const projectId = String(payload.project_id || '').trim();
    const prompt = String(payload.prompt || '');
    const mission = promptValue(prompt, 'PARTIDA');
    const phase = promptValue(prompt, 'FASE');
    const title = String(payload.title || '').trim();
    if (!projectId || !mission || !phase || !title) return null;
    return {projectId, mission, phase, title, key:`${projectId}::${mission}::${phase}::${title}`};
  };

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const matches = (task, identity) => String(task?.title || '').trim() === identity.title
    && promptValue(task?.prompt, 'PARTIDA') === identity.mission
    && promptValue(task?.prompt, 'FASE') === identity.phase;

  const pruneRecent = () => {
    const current = wallNow();
    recentCreations.forEach((entry, key) => {
      if (!entry || entry.expiresAt <= current) recentCreations.delete(key);
    });
  };

  const remember = (identity, result) => {
    if (!identity || !result) return result;
    recentCreations.set(identity.key, {
      identity,
      result,
      taskId: String(result?.id || '').trim(),
      expiresAt: wallNow() + RECENT_CREATION_TTL_MS,
    });
    return result;
  };

  const observeTasks = tasks => {
    if (!Array.isArray(tasks) || !recentCreations.size) return;
    pruneRecent();
    recentCreations.forEach((entry, key) => {
      const visible = tasks.some(task => {
        if (!matches(task, entry.identity)) return false;
        if (entry.taskId) return String(task?.id || '') === entry.taskId;
        return !FAILED.has(normalize(task?.status));
      });
      if (visible) {
        recentCreations.delete(key);
        trace('game-create:visible', {phase:entry.identity.phase, id:entry.taskId || null});
      }
    });
  };

  const recover = async identity => {
    await new Promise(resolve => window.setTimeout(resolve, 250));
    const tasks = await originalApi(
      `/ui/game-tasks?project_id=${encodeURIComponent(identity.projectId)}&limit=24`,
      {method:'GET', timeoutMs:3500, retry:false},
    );
    if (!Array.isArray(tasks)) return null;
    observeTasks(tasks);
    return tasks.find(task => matches(task, identity) && !FAILED.has(normalize(task.status))) || null;
  };

  window.api = async (path, options = {}) => {
    const requestPath = String(path || '');
    const method = String(options.method || 'GET').toUpperCase();

    if (method === 'GET' && (requestPath.startsWith('/tasks?') || requestPath.startsWith('/ui/game-tasks?'))) {
      const result = await originalApi(path, options);
      observeTasks(result);
      return result;
    }

    if (requestPath !== '/tasks' || method !== 'POST') return originalApi(path, options);

    const identity = identityFrom(options);
    if (!identity) return originalApi(path, options);

    pruneRecent();

    const current = locks.get(identity.key);
    if (current) {
      trace('game-create:dedupe', {source:'inflight', phase:identity.phase, title:identity.title});
      return current;
    }

    const recent = recentCreations.get(identity.key);
    if (recent) {
      trace('game-create:dedupe', {source:'recent', phase:identity.phase, title:identity.title, id:recent.taskId || null});
      return recent.result;
    }

    const request = (async () => {
      try {
        trace('game-create:start', {phase:identity.phase, title:identity.title});
        const result = await originalApi(path, options);
        trace('game-create:end', {id:result?.id});
        return remember(identity, result);
      } catch (error) {
        trace('game-create:recover', {message:String(error?.message || error || 'erro')});
        try {
          const recovered = await recover(identity);
          if (recovered) return remember(identity, recovered);
        } catch (recoveryError) {
          trace('game-create:recover-error', {message:String(recoveryError?.message || recoveryError || 'erro')});
        }
        throw error;
      }
    })();

    locks.set(identity.key, request);
    try { return await request; }
    finally { if (locks.get(identity.key) === request) locks.delete(identity.key); }
  };

  window.__devpilotGameTrace = trace;
  window.__devpilotGameCreateDedup = true;
  window.__devpilotGameCreateSequentialDedup = true;
  window.__devpilotGameCreateRecovery = true;
})();
