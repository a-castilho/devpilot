/* DevPilot game v91 — one bounded failure observer; backend owns repair and retest. */
(() => {
  'use strict';
  if (window.__devpilotGameFlowKeeperV91Ready) return;
  window.__devpilotGameFlowKeeperV91Ready = true;

  const FIRST_FAILURE_DELAY_MS = 250;
  const FAILED_POLL_MS = 8000;
  const HIDDEN_FAILED_POLL_MS = 20000;
  const RECOVERY_RECHECK_MS = 30000;
  const TERMINAL_RECOVERY_STATES = new Set([
    'awaiting_intervention',
    'intervention_required',
    'recovery_exhausted',
  ]);

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
  const recoveryFor = state => window.__devpilotGameRecoveryForTask?.(state?.taskId) || null;
  const isTerminalRecovery = recovery => TERMINAL_RECOVERY_STATES.has(String(recovery?.state || ''));
  const missionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task =>
    String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`) &&
    String(task?.id || '') === String(state.taskId || '')
  );
  const fetchTasks = async state => (
    typeof window.api === 'function' && state.projectId
      ? window.api(`/tasks?project_id=${encodeURIComponent(state.projectId)}&limit=500`, {retry: false})
      : []
  );

  const arm = () => {
    window.clearTimeout(timer);
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldWatchFailure(state) || isTerminalRecovery(recoveryFor(state))) {
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

    const existingRecovery = recoveryFor(state);
    if (isTerminalRecovery(existingRecovery)) return arm();

    busy = true;
    try {
      const key = failureKey(state);
      const now = Date.now();
      const lastRecoveryCheck = recoveryChecks.get(key) || 0;

      // Delegate the failure immediately once. Afterwards only re-read/escalate canonical
      // recovery every 30s. This prevents request storms and duplicate repair authority.
      if (!lastRecoveryCheck || now - lastRecoveryCheck >= RECOVERY_RECHECK_MS) {
        try {
          await engine.retry();
          recoveryChecks.set(key, now);
        } catch (error) {
          recoveryChecks.delete(key);
          throw error;
        }

        const recovery = recoveryFor(state);
        if (isTerminalRecovery(recovery)) return;
        const afterRetry = engine.snapshot?.();
        if (!afterRetry?.failed || String(afterRetry.taskId || '') !== String(state.taskId || '')) return;
      }

      // Observe the same original task while the worker repairs/retests it. A status change
      // reloads the controller, which then advances through the normal seven-stage pipeline.
      const tasks = await fetchTasks(state);
      const remote = missionTask(tasks, state);
      if (remote && normalize(remote.status) !== normalize(state.taskStatus)) {
        await window.loadBuildGame?.();
        engine.schedule?.();
      }

      if (recoveryChecks.size > 64) recoveryChecks.delete(recoveryChecks.keys().next().value);
    } catch (error) {
      console.error('[DevPilot Game Flow Keeper]', error);
    } finally {
      busy = false;
      arm();
    }
  }

  document.addEventListener('devpilot:game:state', arm);
  document.addEventListener('devpilot:game:rendered', arm);
  document.addEventListener('devpilot:game:recovery-state', arm);
  document.addEventListener('visibilitychange', arm);
  document.addEventListener('devpilot:game:core-ready', arm);
  arm();
})();
