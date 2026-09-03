/* DevPilot game v82 — make the orchestrator runtime the source of truth for task state. */
(() => {
  'use strict';

  if (window.__devpilotGameRuntimeStateSyncV82Ready) return;
  window.__devpilotGameRuntimeStateSyncV82Ready = true;

  const originalApi = window.api;
  if (typeof originalApi !== 'function') return;

  const STOPPED = new Set(['paused', 'pause_requested', 'canceled', 'cancel_requested', 'archived']);
  let runtimeCache = {at: 0, states: {}};
  let runtimeInFlight = null;

  const now = () => Date.now();
  const taskListRequest = (path, options) => {
    const method = String(options?.method || 'GET').toUpperCase();
    return method === 'GET' && /^\/tasks(?:\?|$)/.test(String(path || ''));
  };

  const loadRuntime = async () => {
    if (now() - runtimeCache.at < 1200) return runtimeCache.states;
    if (runtimeInFlight) return runtimeInFlight;
    runtimeInFlight = Promise.resolve(originalApi('/tasks/orchestrator/runtime', {
      timeoutMs: 5000,
      retry: false,
    }))
      .then(payload => {
        const states = payload && typeof payload.states === 'object' ? payload.states : {};
        runtimeCache = {at: now(), states};
        return states;
      })
      .catch(error => {
        console.warn('[DevPilot Runtime State Sync]', error);
        return runtimeCache.states;
      })
      .finally(() => { runtimeInFlight = null; });
    return runtimeInFlight;
  };

  const effectiveTask = (task, states) => {
    if (!task || typeof task !== 'object') return task;
    const runtime = states?.[String(task.id || '')];
    if (!runtime || !runtime.state) return task;
    const runtimeState = String(runtime.state).trim().toLowerCase();
    const rawStatus = String(task.status || '').trim().toLowerCase();
    const copy = {...task, raw_status: rawStatus, orchestrator_state: runtimeState};

    if (runtimeState === 'archived' || runtimeState === 'canceled' || runtimeState === 'cancel_requested') {
      copy.status = 'canceled';
      copy.failure_reason = runtimeState === 'archived'
        ? 'ORCHESTRATOR_ARCHIVED'
        : `ORCHESTRATOR_${runtimeState.toUpperCase()}`;
      return copy;
    }
    if (runtimeState === 'paused' || runtimeState === 'pause_requested') {
      copy.status = 'blocked';
      copy.failure_reason = `ORCHESTRATOR_${runtimeState.toUpperCase()}`;
      return copy;
    }
    copy.status = runtimeState;
    return copy;
  };

  window.api = async (path, options = {}) => {
    if (!taskListRequest(path, options)) return originalApi(path, options);
    const [rows, states] = await Promise.all([
      originalApi(path, options),
      loadRuntime(),
    ]);
    if (!Array.isArray(rows)) return rows;
    return rows.map(task => effectiveTask(task, states));
  };

  window.__devpilotGameRawApi = originalApi;
  window.__devpilotGameRuntimeStates = () => runtimeCache.states;
})();
