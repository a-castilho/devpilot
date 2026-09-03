/* DevPilot game v88 — bounded failed-state observer; no duplicate healthy polling. */
(() => {
  'use strict';
  if (window.__devpilotGameFlowKeeperV88Ready) return;
  window.__devpilotGameFlowKeeperV88Ready = true;

  const FIRST_FAILURE_DELAY_MS = 250;
  const FAILED_POLL_MS = 8000;
  const HIDDEN_FAILED_POLL_MS = 20000;
  const RECOVERY_RECHECK_MS = 30000;

  let timer = 0;
  let busy = false;
  const recoveryChecks = new Map();

  const controller = () => window.__devpilotGameControllerV73;
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const shouldWatchFailure = state => Boolean(
    state && state.missionId && state.goal && state.taskId && state.failed && !state.done
  );
  const failureKey = state => [
    state?.missionId || 'mission',
    state?.currentPhaseId || 'phase',
    state?.taskId || 'task',
    state?.verifier ? 'gate' : 'phase',
  ].join(':');
  const missionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task =>
    String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`) &&
    String(task?.id || '') === String(state.taskId || '')
  );
  const fetchTasks = async state => (
    typeof window.api === 'function' && state.projectId
      ? window.api(`/tasks?project_id=${encodeURIComponent(state.projectId)}&limit=500`, {retry:false})
      : []
  );

  const arm = () => {
    window.clearTimeout(timer);
    const engine = controller();
    const state = engine?.snapshot?.();

    // Healthy rounds are already refreshed by build-game.js. A second loop here was
    // causing duplicate game-tasks/runtime requests, so flow-keeper is failure-only.
    if (!engine || !shouldWatchFailure(state)) {
      timer = 0;
      return;
    }

    const key = failureKey(state);
    const first = !recoveryChecks.has(key);
    const delay = first
      ? FIRST_FAILURE_DELAY_MS
      : (document.hidden ? HIDDEN_FAILED_POLL_MS : FAILED_POLL_MS);
    timer = window.setTimeout(run, delay);
  };

  async function run() {
    if (busy) return arm();
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldWatchFailure(state)) return arm();

    busy = true;
    try {
      const key = failureKey(state);
      const now = Date.now();
      const lastRecoveryCheck = recoveryChecks.get(key) || 0;

      // Delegate immediately once. If the same task remains failed for a long time,
      // re-check canonical recovery at most once every 30s, never every render/poll.
      if (!lastRecoveryCheck || now - lastRecoveryCheck >= RECOVERY_RECHECK_MS) {
        recoveryChecks.set(key, now);
        await engine.retry();
        const afterRetry = engine.snapshot?.();
        if (!afterRetry?.failed || String(afterRetry.taskId || '') !== String(state.taskId || '')) {
          return;
        }
      }

      const tasks = await fetchTasks(state);
      const remote = missionTask(tasks, state);
      if (remote && normalize(remote.status) !== normalize(state.taskStatus)) {
        await window.loadBuildGame?.();
      }
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
