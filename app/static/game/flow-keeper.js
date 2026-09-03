/* DevPilot game v87 — observer only; canonical backend owns failure recovery. */
(() => {
  'use strict';
  if (window.__devpilotGameFlowKeeperV87Ready) return;
  window.__devpilotGameFlowKeeperV87Ready = true;

  const VISIBLE_DELAY_MS = 2500;
  const HIDDEN_DELAY_MS = 8000;
  const FAILED_DELAY_MS = 1800;
  let timer = 0;
  let busy = false;
  const controller = () => window.__devpilotGameControllerV73;
  const delay = state => state?.failed ? FAILED_DELAY_MS : (document.hidden ? HIDDEN_DELAY_MS : VISIBLE_DELAY_MS);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const shouldKeepMoving = state => Boolean(state && state.missionId && state.goal && !state.done);
  const missionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task => String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`) && String(task?.id || '') === String(state.taskId || ''));
  const missionTasks = (tasks, state) => (Array.isArray(tasks) ? tasks : []).filter(task => String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`));
  const fetchTasks = async state => typeof window.api === 'function' && state.projectId ? window.api(`/tasks?project_id=${encodeURIComponent(state.projectId)}&limit=500`) : [];

  const arm = () => {
    window.clearTimeout(timer);
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) return void (timer = 0);
    timer = window.setTimeout(run, delay(state));
  };

  async function run() {
    if (busy) return arm();
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) return arm();
    busy = true;
    try {
      // A failed phase must never create another game task. recovery-runtime delegates the SAME
      // failed task to /recovery/escalate; worker fixes it and requeues the original task.
      if (state.failed) {
        await engine.retry();
        await engine.refresh();
        return;
      }
      const tasks = await fetchTasks(state);
      if (!state.hasTasks) {
        if (missionTasks(tasks, state).length && typeof window.loadBuildGame === 'function') {
          await window.loadBuildGame();
          engine.schedule?.();
        }
        return;
      }
      const remote = missionTask(tasks, state);
      if (remote && normalize(remote.status) === normalize(state.taskStatus)) return;
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
