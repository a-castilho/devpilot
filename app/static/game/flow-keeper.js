/* DevPilot game v77 — browser only observes server-side round progression. */
(() => {
  'use strict';

  if (window.__devpilotGameFlowKeeperV77Ready) return;
  window.__devpilotGameFlowKeeperV77Ready = true;

  const VISIBLE_DELAY_MS = 2500;
  const HIDDEN_DELAY_MS = 8000;
  let timer = 0;
  let busy = false;

  const controller = () => window.__devpilotGameControllerV73;
  const delay = () => document.hidden ? HIDDEN_DELAY_MS : VISIBLE_DELAY_MS;
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  const shouldWatch = state => Boolean(
    state && state.missionId && state.goal && !state.done
  );

  const fetchTasks = async state => {
    if (typeof window.api !== 'function' || !state.projectId) return [];
    return window.api(`/tasks?project_id=${encodeURIComponent(state.projectId)}&limit=500`, {retry:false});
  };

  const missionTasks = (tasks, state) => (Array.isArray(tasks) ? tasks : []).filter(task =>
    String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`)
  );

  const signature = tasks => tasks
    .map(task => `${task.id}:${normalize(task.status)}`)
    .sort()
    .join('|');

  let lastSignature = '';

  const arm = () => {
    window.clearTimeout(timer);
    const state = controller()?.snapshot?.();
    if (!shouldWatch(state)) {
      timer = 0;
      return;
    }
    timer = window.setTimeout(run, delay());
  };

  async function run() {
    if (busy) return arm();
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldWatch(state)) return arm();

    busy = true;
    try {
      const tasks = missionTasks(await fetchTasks(state), state);
      const remoteSignature = signature(tasks);
      if (!remoteSignature || remoteSignature === lastSignature) return;
      lastSignature = remoteSignature;

      // Important: the browser never creates gates or next phases. The worker-side
      // GameRoundOrchestrator owns progression. We only repaint after a real change.
      if (typeof window.loadBuildGame === 'function') await window.loadBuildGame();
    } catch (error) {
      console.error('[DevPilot Game Observer]', error);
    } finally {
      busy = false;
      arm();
    }
  }

  document.addEventListener('devpilot:game:state', arm);
  document.addEventListener('visibilitychange', arm);
  document.addEventListener('devpilot:game:core-ready', arm);
  arm();
})();
