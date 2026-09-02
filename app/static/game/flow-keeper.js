/* DevPilot game v76 — passive state watcher: keeps the real pipeline moving without repainting the UI on every poll. */
(() => {
  'use strict';

  if (window.__devpilotGameFlowKeeperV76Ready) return;
  window.__devpilotGameFlowKeeperV76Ready = true;

  const VISIBLE_DELAY_MS = 2500;
  const HIDDEN_DELAY_MS = 8000;
  let timer = 0;
  let busy = false;

  const controller = () => window.__devpilotGameControllerV73;
  const delay = () => document.hidden ? HIDDEN_DELAY_MS : VISIBLE_DELAY_MS;
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  const shouldKeepMoving = state => Boolean(
    state && state.missionId && state.goal && !state.done && !state.failed
  );

  const missionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task => {
    const prompt = String(task?.prompt || '');
    return prompt.includes(`PARTIDA: ${state.missionId}`) && String(task?.id || '') === String(state.taskId || '');
  });

  const anyMissionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task =>
    String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`)
  );

  const fetchTasks = async state => {
    if (typeof window.api !== 'function' || !state.projectId) return [];
    return window.api(`/tasks?project_id=${encodeURIComponent(state.projectId)}&limit=500`);
  };

  const arm = () => {
    window.clearTimeout(timer);
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) {
      timer = 0;
      return;
    }
    timer = window.setTimeout(run, delay());
  };

  async function run() {
    if (busy) return arm();
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) return arm();

    busy = true;
    try {
      const tasks = await fetchTasks(state);

      // Start POST can return before /tasks exposes the created task.
      // Poll silently until it is visible; only then synchronize/render once.
      if (!state.hasTasks) {
        if (anyMissionTask(tasks, state) && typeof window.loadBuildGame === 'function') {
          await window.loadBuildGame();
          engine.schedule?.();
        }
        return;
      }

      // While the current task keeps the same status, do absolutely nothing to the DOM.
      // This removes the 2.5s full-screen blink while preserving polling.
      const remote = missionTask(tasks, state);
      if (remote && normalize(remote.status) === normalize(state.taskStatus)) return;

      // A real transition happened (queued→running→completed, gate, next phase, etc.).
      // Let the existing controller synchronize once and advance the real pipeline.
      await engine.refresh();
      engine.schedule?.();
    } catch (error) {
      console.error('[DevPilot Game Flow Keeper]', error);
    } finally {
      busy = false;
      arm();
    }
  }

  document.addEventListener('devpilot:game:state', arm);
  document.addEventListener('devpilot:game:rendered', arm);
  document.addEventListener('visibilitychange', arm);
  document.addEventListener('devpilot:game:core-ready', arm);
  arm();
})();
